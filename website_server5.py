from bottle import route, post, run, redirect, abort, static_file, template, request, response
import requests
import os
import enum
import socket
import json
import secrets
import uuid
import time
import Calc_farm_main_server_db_connector as Db
from datetime import datetime


PORT = 6060
server_port = 8080
TIMEOUT = 3

def raise_http_error(status_name, status_details=None):
    """
    This function sends an HTTP error message to the client after he did an act the server can't or won't handle
    and ends the communication of him/her with the server.
    :param status_name: the offical status name(that is in the dictionary of status codes that the server was configured
    to handle: "HTTPSTATUSCODES") of the existing status code.
    :param status_details: additional details that specify what went wrong.
    """
    status_message = Db.HTTPSTATUSMESSAGES[status_name]
    if status_details is not None:
        status_message += ':' + status_details

    if status_name in Db.HTTPSTATUSCODES:
        abort(Db.HTTPSTATUSCODES[status_name], status_message)


def handle_path(path):
    valid_path = '/'.join(list(filter(lambda x: len(x) > 0, path.replace('\\', '/').split("/"))))
    # print(valid_path)
    # print(os.path.isfile(valid_path))
    return valid_path


def package_data(data_dict):
    """
    This function packages data to a Json file to send to the client.
    :param data_dict: dictionary that contains data to send to the client
    :return: a json file of the data
    """
    return json.dumps(data_dict)


def recieve_information_from_work_server():
    """
    This function receives a 'POST' request method from a work server and get it's data
    :return: the data the work server sent in the POST request(as a part of their protocol, the work server
    sends its data in the "json" header,
    where there is its data in the form of a json file) in the form of a dictionary.
    """
    client_data = request.forms.get('json')
    client_data_dict = json.loads(client_data)
    return client_data_dict


def connect_to_work_server(task_name, route_url=None, input_list=None):
    """
    This function sends 'get' request to one of the routes on one of the work servers.
    :param task_name: The name of the task the work server is working on.
    :param route_url: a string of the url of the route
    :param input_list: a list of all the inputs to the route(the number of inputs need to match the number
    of the route's arguments)
    :return: the output from the server- a JSON file the was converted to a dictionary.
    (all the clients to a server communicate to it using JSON files as a part of the protocol)
    """
    if input_list is None:
        input_list = []

    #input_list = [key] + input_list

    if route_url is None:
        route_url = ''
    work_server_ip = Db.get_server_ip(task_name, get_user_from_session())
    if work_server_ip is not None:
        url_to_server = "http://" + work_server_ip + ':' + str(server_port) + '/communication/main_server/' + route_url
    #The server port has its own slashes and they will be removed by the function and make an invalid url
        for server_input in input_list:
            if len(str(server_input)) > 0:
                url_to_server = url_to_server + '/' + str(server_input)

        req = None
        try:
            req = requests.get(url=url_to_server, timeout=TIMEOUT)
        # if 'text' in str(req.headers.get('content-type').lower())
        # or 'html' in str(req.headers.get('content-type').lower()):
        #print(req.content)

            req.raise_for_status()
            return req
        except requests.exceptions.HTTPError:
            http_name = Db.HTTPSTATUSCODESDECODER[req.status_code]
            print("HTTP error of " + str(req.status_code) + "- " + http_name + ': \n' + Db.HTTPSTATUSMESSAGES[http_name])
        except requests.exceptions.ConnectTimeout:
            print("The main server didn't respond")
        except requests.exceptions.RequestException as e:
            print('There was an error in communication: ' + str(e))




def recieve_data_from_server(task_name, route_url=None, input_list=None):
    """
    The work server gets data from a route on the main server as a JSON file according to it protocol:
    :param route_url: the url where the wanted route is
    :param input_list: a list of all the inputs to the route(the number of inputs need to match the number
    of the route's arguments)
    :return: the output from the route in the form of a dictionary that was a JSON file

    """
    raw_data = connect_to_work_server(task_name, route_url, input_list)
    if raw_data is None:
        return None
    else:
        return raw_data.json()




def identify(user_name, return_data=False):
    if Db.find_user(user_name):
        if return_data:
            return Db.find_user(user_name, return_data=True)
    else:
        print("sorry " + user_name)
        raise_http_error("Unauthorized", "The user name doesn't exist")

main_directory = handle_path(os.getcwd())
website_folder = 'website'
website_dir = main_directory + '/' + website_folder
pages_folder = 'pages'
images_folder = 'images'
script_folder = 'code_pages'
exe_folder = 'exe_of_tasks'


def create_folder(folder_name):
    folder_path = handle_path(main_directory + '/' + folder_name)
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path)


create_folder(website_folder)
create_folder(website_folder + '/' + pages_folder)
create_folder(website_folder + '/' + images_folder)
create_folder(website_folder + '/' + script_folder)
create_folder( '/' + exe_folder)
base_dir = website_dir + '/' + pages_folder + '/base.html'
base_form_dir = website_dir + '/' + pages_folder + '/base_form.html'


def convert_args_to_route(args):
    route_args = ''
    for arg in args:
        route_args = route_args + '/<' + arg + '>'
    return route_args


task_form_current = {}


def form_reader(form_data):
    form_values = {}
    for form_line in form_data:
        form_name = form_line['form_name']
        form_values[form_name] = request.forms.get(form_name, type=form_line['input_type'])
    return form_values


def form_handler(answer_route, form_data, default_value):
    if len(task_form_current) > 0:
        default_value = task_form_current
    accepts_file = False
    for form_line in form_data:
        if form_line['form_name'] in default_value:
            form_line['default_value'] = default_value[form_line['form_name']]
        if form_line['type'] == 'file':
            accepts_file = True
    return {'post_route': answer_route, 'has_text_line': accepts_file, 'form_details': form_data,
            'base_form_file': base_form_dir}


def generate_session_id(id_length=16):
    return secrets.token_urlsafe(id_length)


def write_session(username):
    #response.set_cookie("visited", "yes", secret="some secret key)
    session_id = generate_session_id()
    response.set_cookie("sid", session_id, path="/")
    #response.set_cookie("sid", "AAAA")
    Db.create_session(session_id, username, get_sid())


def get_user_from_session():
    sid = get_sid()
    if sid:
        return Db.find_user_name_by_sid(sid)
    else:
        return None


def get_sid():
    return request.get_cookie("sid")


def close_session():
    #response.delete_cookie("visited")
    Db.delete_session(get_sid())
    response.set_cookie("sid", "", path="/")


def get_to_url():
    url = request.get_cookie("prev_route")
    #response.delete_cookie("prev_route")
    response.set_cookie("prev_route", "", path="/")
    if url:
        redirect(url)
    else:
        redirect("/home")


def login_answers_handler():
    form_values = form_reader(Db.login_form_details)
    user_data = Db.find_user_name_by_password_checking(form_values["user_name"], form_values["password"])
    if user_data:
        write_session(form_values["user_name"])
        time.sleep(2)
        get_to_url()

    else:
        raise_http_error("Unauthorized", "Wrong user details")


def menu_handler():
    return {"task_list": Db.get_all_tasks_by_user(get_user_from_session())}


def running_menu_handler():
    return {"running_task_list": Db.get_all_running_tasks_by_user(get_user_from_session()),
            "status_decoder": Db.task_status_names_list}


def logout():
    close_session()
    get_to_url()


routes = {
    'home': {'link_name': 'home', 'html_file_name': 'home.html', 'route_type': 'navigation_page',
             'handling_function': form_handler,
             'args': ('/input/task_form', Db.task_form_details,
                      {'task_name': 'Default_TaskName', 'first_num': 0, 'last_num': 100})},

    'signup': {'link_name': 'signup', 'html_file_name': 'signup.html', 'route_type': 'navigation_page',
             'handling_function': form_handler, 'button_direction': 'right',
              'args': ('/input/signup_form', Db.signup_form_details,
                      {'user_name': 'Default_UserName'})},

    'login': {'link_name': 'login', 'html_file_name': 'login.html', 'route_type': 'navigation_page',
             'handling_function': form_handler,
              'args':('/input/login_form', Db.login_form_details, {'user_name': 'Default_UserName'})},

'tasks': {'link_name': 'tasks', 'html_file_name': 'signup.html', 'route_type': 'navigation_page',
             'handling_function': lambda: redirect('/tasks/menu'), 'needs_username': True, "inner_routes":
              ['menu', 'run_task', 'create_task', 'running_tasks']},
'tasks/menu': {'link_name': 'tasks', 'html_file_name': 'tasks_list.html', 'route_type': 'inner_page',
               'needs_username': True, 'handling_function':menu_handler},
'tasks/running_tasks': {'link_name': 'tasks', 'html_file_name': 'running_tasks_list.html', 'route_type': 'inner_page',
               'needs_username': True, 'handling_function': running_menu_handler},
'tasks/create_task': {'link_name': 'tasks', 'html_file_name': 'tasks_list.html', 'route_type': 'inner_page',
               'needs_username': True},
'tasks/task_menu': {'link_name': 'tasks', 'html_file_name': 'task_menu.html', 'route_type': 'inner_page',
               'needs_username': True},
'tasks/task_stats': {'link_name': 'tasks', 'html_file_name': 'task_stats.html', 'route_type': 'inner_page',
               'needs_username': True},
'logout': {'link_name': 'logout', 'route_type': 'navigation_page', 'handling_function': logout}


}


routes_website_dict = {}
for route_name in routes:
    routes_website_dict[route_name] = routes[route_name]['link_name']
    #'download':['download.html',download_handler],
    #'create';


def get_website_file(file_name, sub_dir="", info_args=None):
    """
    This function uses the template engine to return a file to the webstite
    :param file_name: the full file name(and , it needs to be
    a part of the dir, so the template can reach it
    :param sub_dir:if the file is in another folder inside the root folder 'website', then this is a directory
    linking from the root to the file.
    :param info_args:a dictionary filed with values for the template to insert into the HTML file.
    :return:
    """
    file_dir = handle_path(website_dir + '/' + sub_dir + '/' + file_name)
    if os.path.isfile(file_dir):
        if info_args is None:
            print(template(file_dir))
            return template(file_dir)
        print(template(file_dir, info_args))
        return template(file_dir, info_args)
    else:
        raise_http_error("Not Found")


def route_handler(route_name, args=None):
    """
    This function returns a page of a route on the website,
    including it's templates for the navigation bar, and more....
    :param route_name:The name of the route that is linked to the pages in the "routes" dictionary.
    :param args: A dictionary with more values to insert into the html page
    """
    print('handling ' + route_name)
    print("user" + str(get_user_from_session()))
    template_dict = {
        'nav_route_dict': routes,
        'nav_current_route': route_name,
        'base_file': base_dir,
        'user_name': get_user_from_session()
    }
    if 'needs_username' in routes[route_name]:
        if routes[route_name]['needs_username']:
            if not get_user_from_session():
                if args is not None:
                    template_dict.update(args)
                template_dict['prev_route'] = route_name
                return get_website_file('needs_user.html', pages_folder, template_dict)


    if 'handling_function' in routes[route_name]:
        if 'args' in routes[route_name]:
            template_dict.update(routes[route_name]['handling_function'](*routes[route_name]['args']))
        else:
            template_dict.update(routes[route_name]['handling_function']())
    if args is not None:
        template_dict.update(args)
    return get_website_file(routes[route_name]['html_file_name'], pages_folder, template_dict)


@route('/')
def index():
    print('a client joined')
    redirect('/home')
    #redirect('/signup')
    #return get_website_file('index.html', pages_folder,{'route_name':'img_link'})


@route('/<nav_route_name>')
def navigation_routes_handler(nav_route_name):
    #if nav_route_name.endswith('.css'):

    #elif nav_route_name.endswith('.css'):

    if nav_route_name in routes:
        if routes[nav_route_name]['route_type'] == 'navigation_page':
            return route_handler(nav_route_name)
    raise_http_error("Not Found")

@route('/<route_name>/<inner_path>')
def inner_page_handler(route_name, inner_path):
    full_route = "{}/{}".format(route_name, inner_path)
    if route_name in routes:
        if "inner_routes" in routes[route_name]:
            if inner_path in routes[route_name]["inner_routes"] and full_route in routes:
                return route_handler(full_route)
    raise_http_error("Not Found")

"""
@route('/hello')
def hello_again():
    
    now = datetime.now()
    if request.get_cookie("visited"):
        response.set_cookie("visited", "yes" + now.strftime("%H:%M:%S"))
        return "Welcome back! Nice to see you again" + now.strftime("%H:%M:%S")
    else:
        response.set_cookie("visited", "yes" + now.strftime("%H:%M:%S"))
        return "Hello there! Nice to meet you" +now.strftime("%H:%M:%S")
    
    print("hi")
    write_session("aaaa", "5")
"""

@post('/input/signup_form')
def signup_form_input():
    signup_form_current = form_reader(Db.signup_form_details)
    try:
        Db.insert_user(signup_form_current["user_name"], signup_form_current["password"])
        write_session(signup_form_current["user_name"])
        get_to_url()
        #redirect('/home')
    except Db.MainServerError as e:
        raise_http_error("Unauthorized", e.args[0])

@post('/input/login_form')
def signup_form_input():
    login_answers_handler()
#@route('/images' + convert_args_to_route(route['images'][RouteArgNames.handling_function.Value].__code__.co_varnames))


@route('/images/<image_name>')
def image_handler(image_name):
    img_dir = handle_path(website_dir + '/' + images_folder)
    if os.path.isfile(img_dir + '/' + image_name):
        return static_file(image_name, root=img_dir)
    else:
        raise_http_error("Not Found")


@route('/tasks/<task_name>/task_menu')
def task_menu(task_name):
    return route_handler('tasks/task_menu',{"task": task_name})


@route('/tasks/<task_name>/task_run')
def task_run(task_name):
    Db.start_working_on_a_task(get_user_from_session(), task_name)
    get_to_url()


@route('/tasks/<task_name>/cancel_task')
def cancel_running_task(task_name):
    recieve_data_from_server(task_name, route_url="stop_working")
    Db.cancel_working_on_task(get_user_from_session(), task_name)
    get_to_url()


@route('/tasks/<task_name>/task_stats')
def get_task_stats(task_name):
    stats = recieve_data_from_server(task_name, route_url="get_stats")
    if stats is None:
        stats = {"progress_precent": 0, "results": ""}
    results = Db.get_results(get_user_from_session(), task_name)
    if results is not None:
        stats["results"] = results
    return route_handler("tasks/task_stats", stats)


@route('/scripts/<script_name>')
def script_handler(script_name):
    return get_website_file(script_name, script_folder)

#Communication

@route('/communication/work_server/<user_name>')
def test(username):
    identify(username)
    return package_data({"Message":"bruh"})


@route('/communication/work_server/get_task/<user_name>')
def get_task(user_name):
    identify(user_name)
    saved_task = Db.get_free_tasks(user_name)
    if saved_task is None:
        return package_data(None)
    else:
        server_ip = request.environ.get('HTTP_X_FORWARDED_FOR') or request.environ.get('REMOTE_ADDR')
        print(str(saved_task["Task_name"]) + ": " + str(saved_task))
        Db.assign_task(user_name, saved_task["Task_name"], server_ip)
        return package_data(saved_task)

@route('/communication/work_server/lol/<user_name>/<message>')
def lol(user_name,message):
    return "lol" + message

@route('/communication/work_server/getexefile/<user_name>/<requested_exe_name>')
def getexefile(user_name, requested_exe_name):
        """
        The exe filenames are built from the exe name and the name of the user that created it.
        "{Exe name}.exe:{username}"
        (A user can't have two exe files with the same name).
        :param user_name:The name of the user that created the exe_name.
        :param requested_exe_name:The name of the Exe file
        :return:
        """
        identify(user_name)
        file_dir = handle_path(main_directory + '/' + exe_folder)

        # data_to_worker = {'file': static_file(filename, root=file_dir, download=filename)}
        # return package_data(data_to_worker)
        if requested_exe_name.endswith('.exe'):
            requested_exe_name = requested_exe_name[:-4]
        file_name = requested_exe_name + "&" + str(user_name) + '.exe'
        if not os.path.isfile(handle_path(file_dir + '/' + file_name)):
            print("The server didn't find the file.")
            raise_http_error("Not Found")
        return static_file(file_name, root=file_dir, download=requested_exe_name)

@post('/communication/work_server/get_results/<user_name>')
def get_results(user_name):
    print("getting results")
    identify(user_name)
    server_ip = request.environ.get('HTTP_X_FORWARDED_FOR') or request.environ.get('REMOTE_ADDR')

    results_dict = recieve_information_from_work_server()
    if results_dict is not None:
        Db.set_results(user_name, server_ip, results_dict["results"])

@route('/communication/worker/get_task/<user_name>')
def get_task(user_name):
    identify(user_name)
    print("got task")
    available_task = Db.assign_worker(user_name)
    return available_task



    #return package_data({"Message": "Congradulations"})
def main():
    hostname = socket.gethostname()
    IPAddr = socket.gethostbyname(hostname)
    print("Server {} of IP {} is ready to go!".format(hostname, IPAddr))

    print("http://" + IPAddr + ':' + str(PORT))
    run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    main()