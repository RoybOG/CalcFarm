from bottle import route, run, post, request, abort, static_file, redirect
import requests
import uuid
import json
import socket
import os
import sys
import time
import Calcfarm_server_database_connector as Db

TIMEOUT = 3
PORT = 8080
MAIN_SERVER_PORT = 6060
#The main server should have a different port from the rest of the work server to distinguish
#itself.
ARGS = sys.argv
if len(ARGS) == 0:
    print("Something is wrong.")
    sys.exit(-1)
else:
    ARGS = ARGS[1:]
    if len(ARGS) == 0:
        print("You didn't insert your user name as as argument.")
        sys.exit(-1)

username = ARGS[0]

Main_Server_IPAddr = "10.0.0.7"
Main_Server_url = "http://" + Main_Server_IPAddr + ':' + str(MAIN_SERVER_PORT)


global exe_name
global Task_Conditional
work_units_amount = 0
finished_work_units_amount = 0
WORK_UNIT_LENGTH = 1000
work_status = Db.WorkStatusNames.no_work.value
global time_start, time_end
started_working = False

num_of_computers = 0
HTTPSTATUSCODES = {"Bad Request": 400,
                   "Unauthorized": 401,
                   "Forbidden": 403,
                   "Not Found": 404,
                   "Not Allowed": 405,
                   "I'm a teapot": 418,
                   "Internal Server Error": 500
                   }

HTTPSTATUSCODESDECODER = {400:"Bad Request",
                   401: "Unauthorized",
                   403:"Forbidden",
                   404:"Not Found",
                   405:"Not Allowed",
                   418:"I'm a teapot",
                   500:"Internal Server Error"
                   }
HTTPSTATUSMESSAGES = {"Bad Request": "The server did not recognise the command",
                      "Unauthorized": "The server doesn't recognise you.",
                      "Forbidden": "You aren't qualified to get access to this service",
                      "Not Found": "The resource you asked for doesn't exist.",
                      "Not Allowed": "Your http request was invalid",
                      "I'm a teapot": "I'm sorry kind sir, I can't offer you tea!",
                      "Internal Server Error": "There was an error in a process inside the server"
                      }


def handle_path(path):
    path_args = (path.replace('\\', '/')).split("/")
    valid_path = path_args[0]
    for path_arg in path_args[1:]:
        if len(str(path_arg)) > 0:
            valid_path = valid_path + '/' + str(path_arg)
    return valid_path


def create_folder(folder_dir):
    folder_path = handle_path(folder_dir)
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path)


exe_folder = 'tasks'
main_directory = os.getcwd().replace('\\', '/')
exe_dir = main_directory + '/' + exe_folder
# The folder with all of the website files is saved in the current working directory(cwd),
# the directory where the ".py" file of this program is.
create_folder(exe_dir)


#Send Functions:

def connect_to_route(route_url=None, input_list=None):
    """
    This function sends 'get' request to one of the routes on the main server
    :param route_url: a string of the url of the route
    :param input_list: a list of all the inputs to the route(the number of inputs need to match the number
    of the route's arguments)
    :return: the output from the server- a JSON file the was converted to a dictionary.
    (all the clients to a server communicate to it using JSON files as a part of the protocol)
    """
    if input_list is None:
        input_list = []

    input_list = [username] + input_list

    if route_url is None:
        route_url = ''

    url_to_server = Main_Server_url + '/communication/work_server/' + route_url
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
        http_name = HTTPSTATUSCODESDECODER[req.status_code]
        raise Db.WorkerServerError("HTTP error of " + str(req.status_code) + "- " + http_name + ': \n' +
                                   HTTPSTATUSMESSAGES[http_name])
    except requests.exceptions.ConnectTimeout:
        raise Db.WorkerServerError("The main server didn't respond")
    except requests.exceptions.RequestException as e:
        raise Db.WorkerServerError('There was an error in communication: ' + str(e))


def send_to_server(route_url, data_dict, input_list=None):
    """
     This function sends 'post' request to one of the routes on the server
    :param route_url: a string of the url of the route
    :param data_dict: the data that the worker wants to send to the server in the form of a dictionary
    that is too big to be sent normally as an argument.
    :param input_list: a list of all the inputs to the route(the number of inputs need to match the number
    of the route's arguments)
    :return: the output from the route in the form of a dictionary that was a JSON file
    """
    json_to_send = package_data(data_dict)

    if input_list is None:
        input_list = []

    input_list = [username] + input_list

    route_url = handle_path(route_url)

    url_to_server = Main_Server_url + '/communication/work_server/' + route_url
    dir_args = [] + input_list
    for worker_input in dir_args:
        if len(str(worker_input)) > 0:
            url_to_server = url_to_server + '/' + str(worker_input)

    req = None
    try:
        req = requests.post(url=url_to_server, data={'json': json_to_send})
        req.raise_for_status()
        return req
    except requests.exceptions.HTTPError:
        print("url {} cuased an error".format(url_to_server))
        print("HTTP error of " + str(req.status_code) + "- " + HTTPSTATUSCODESDECODER[req.status_code]
                          + ': \n' + HTTPSTATUSMESSAGES[HTTPSTATUSCODESDECODER[req.status_code]])
    except requests.exceptions.ConnectTimeout:
        print("The server didn't respond")
    except requests.exceptions.RequestException as e:
        print('There was an error in communication: ' + str(e))


def recieve_data_from_server(route_url=None, input_list=None):
    """
    The work server gets data from a route on the main server as a JSON file according to it protocol:
    :param route_url: the url where the wanted route is
    :param input_list: a list of all the inputs to the route(the number of inputs need to match the number
    of the route's arguments)
    :return: the output from the route in the form of a dictionary that was a JSON file

    """
    raw_data = connect_to_route(route_url, input_list)
    if raw_data is None:
        return None
    else:
        return raw_data.json()


def get_file(requested_exe_name):
    """
    In this function, the worker gets he exe.file
    :return: A unique ID of a hexadecimal string that the worker will use to identify itself to the server.
    """

    file_data = connect_to_route("getexefile", input_list=[requested_exe_name])
    if not requested_exe_name.endswith('.exe'):
        requested_exe_name = requested_exe_name + '.exe'
    download_folder_dir = handle_path(main_directory + '/' + exe_folder + '/' + requested_exe_name)
    if not os.path.isdir(main_directory + '/' + exe_folder):
        create_folder(exe_folder)
    try:
        with open(download_folder_dir, 'wb') as file_creator:
            file_creator.write(file_data.content)
    except OSError:
        print("The program couldn't recreate the .exe file")


#Output funcitons


def task_divider(first_num, last_num):
    """
    This function divides the total amount of numbers to small work unit of constant amount.
    :param first_num: the smallest number in the entered number range(including that number).
    :param last_num: the bigest number in the entered number range(including that number).
    """

    num_amount = last_num - first_num + 1
    index = first_num
    reminder = num_amount % WORK_UNIT_LENGTH
    global work_units
    global work_units_amount
    global work_status
    while index - 1 + WORK_UNIT_LENGTH <= last_num - reminder:
        work_unit_data = {
            "first_num": index,
            "last_num": index - 1 + WORK_UNIT_LENGTH,
        }
        Db.insert_work_unit(work_unit_data)
        work_units_amount = work_units_amount + 1
        index = index + WORK_UNIT_LENGTH

    if reminder > 0:
        work_unit_data = {
            "first_num": last_num - reminder + 1,
            "last_num": last_num
        }
        Db.insert_work_unit(work_unit_data)
        work_units_amount = work_units_amount + 1
    work_status = Db.WorkStatusNames.has_work.value
    #print(work_units)


def recieve_information_from_client():
    """
    This function receives a 'POST' request method from a client and get it's data
    :return: the data the client sent in the POST request(as a part of their protocol, the client sends its data
    in the "json" header, where there is its data in the form of a json file) in the form of a dictionary.
    """
    client_data = request.forms.get('json')
    client_data_dict = json.loads(client_data)
    return client_data_dict


def raise_http_error(status_name, status_details=None):
    """
    This function sends an HTTP error message to the client after he did an act the server can't or won't handle
    and ends the communication of him/her with the server.
    :param status_name: the offical status name(that is in the dictionary of status codes that the server was configured
    to handle: "HTTPSTATUSCODES") of the existing status code.
    :param status_details: additional details that specify what went wrong.
    """

    status_message = HTTPSTATUSMESSAGES[status_name]
    if status_details is not None:
        status_message += ':' + status_details

    if status_name in HTTPSTATUSCODES:
        abort(HTTPSTATUSCODES[status_name], status_message)


def read_file(root, file_name, file_type='t'):
    """
    This function finds a file in the 'root' folder with the corresponding name,
    and reads its content depending on it's type.

    :param root: the folder in which the file is: if it is 'website', then it's a html file to the website
    and if it is 'exefile' then it's the executable file.

    :param file_name: the name of the text file(including the file type at the end, which in this case is '.txt')
    that has the html of the wanted page.

    :param file_type: the type of file's content.  't' for text files, 'b' for binary files.
    By default, it would assume the file is a text file.
    :return: the html code that was stored on the file as a string
    """

    page_dir = handle_path(main_directory + '/' + root + '/' + file_name)

    try:
        # if type != 'b' and type != 't':
            # raise
        with open(page_dir, 'r' + file_type) as page_reader:
            return str(page_reader.read())
    except FileNotFoundError:
        print("The file the user requested doesn't exist")
        raise_http_error("Not Found")
    except OSError:
        print("The server couldn't get the page file")
        raise_http_error("Internal Server Error")


def id_generator():
    """
    This function generates an ID for A computer that sign up and wants to join and conribute.
    It uses the uuid function to generate huge unique and random strings.
    :return: a unique and long hexadecimal string that
    """
    new_id = uuid.uuid4()
    return new_id.hex


def identify(sus_id):
    """
    This function checks if a worker with this id exists in the database.
    if it doesn't exists, it will send an "Unauthorized" status error,
    it it does exists, it will return data it has about the worker.
    The worker will always send its id as the first argument to every route.

    :param sus_id: the suspicious id the program wants to check

    :return: returns data about the worker if it exists.
    """
    worker_data = Db.find_worker(sus_id)
    if worker_data is None:
        raise_http_error("Unauthorized")

    return worker_data


def package_data(data_dict):
    """
    This function packages data to a Json file to send to the client.
    :param data_dict: dictionary that contains data to send to the client
    :return: a json file of the data
    """
    return json.dumps(data_dict)


#@route('communication/startworking/<firstnum>/<lastnum>', mathod='POST')
def startworking():
    """
    When the user will enter the executable file, the first number and last number in the range, the server
    will first devide
    :param task_file_name: the name of the exe file the program wants to run on all the numbers in the range.
    The heart of the task(including the ending of '.exe').
    :param first_num:The smallest number in the desired number range, the first number.
    :param last_num:The biggest number in the desired number range, the first number.
    """
    #In the future have the manager program or from the website implement this arguments to a route
    #the program will download the file from the website
    global exe_name
    global Task_Conditional
    task_data = None
    while task_data is None:
        task_data = recieve_data_from_server("get_task")
        if task_data is None:
            time.sleep(5)
        else:
            exe_name = task_data["exe_name"]
            print('Working on the task "{}"'.format(exe_name))
            get_file(exe_name)
            Task_Conditional = task_data["Task_conditional"]
            print("loading")
            t1 = time.time()
            task_divider(task_data["first_num"], task_data["last_num"])
            t2 = time.time()
            print("ready {}".format(t2-t1))

@route('/')
def lol():
    print('lol')
    return 'lol'


@route('/communication/worker/signup')
def signup():
    """
    The worker who communicated to this server for the first time, will get
    :return:
    """
    if work_status == Db.WorkStatusNames.finished_work.value:
        raise_http_error("Forbidden", "This server doesn't need anymore workers, it finished it's job")
    new_worker_id = str(id_generator())
    print("New worker entered " + new_worker_id)
    sign_up_data = {"worker_id": new_worker_id,
                    "worker_ip": request.environ.get('HTTP_X_FORWARDED_FOR') or request.environ.get('REMOTE_ADDR')
                    }
    Db.insert_worker(sign_up_data)
    return package_data({"id": new_worker_id})


@route('/communication/worker/getworkunit/<worker_id>')
def getworkunit(worker_id):
    """
    The server gets the worker an available work unit to work on.

    :param worker_id:
    :return:if it finds a work unit, it would send a JSON file of the work unit and it's information,
            but if it didn't find, it would send a message detailing to it why it couldn't find.
    """

    worker_data = identify(worker_id)
    global time_start
    global started_working
    global work_status
    if work_status == Db.WorkStatusNames.has_work.value:

        saved_work_unit = Db.get_free_work_unit()
        if saved_work_unit is None:
            work_status = Db.WorkStatusNames.no_work.value
        else:
            if not started_working:
                time_start = time.time()
                started_working = True
                #It counts it's
            print(str(saved_work_unit["work_unit_id"]) + " " + str(saved_work_unit))
            Db.assign_work_unit(saved_work_unit["work_unit_id"], worker_id)
            return saved_work_unit



    return package_data({"fail_message": work_status})

@route('/lol')
def a():
    return "lol"

@post('/communication/worker/update/<worker_id>')
def update(worker_id):
    worker_data = identify(worker_id)
    global finished_work_units_amount
    global work_status
    global time_end
    worker_log_dict = recieve_information_from_client()
    worker_work_unit = Db.get_work_unit_by_worker(worker_id)

    if worker_log_dict['status'] == 1:

        if worker_work_unit is None:
            raise_http_error("Bad Request", "A worker who has no work unit assigned to it, can't do an update")
        work_unit_id = worker_work_unit['work_unit_id']

        work_unit_results = worker_log_dict['results']
        #if work_units[data_dict['status']] == WorkUnitStatusNames.in_progress.value:
        if worker_work_unit["work_unit_status"] == Db.WorkUnitStatusNames.in_progress.value:
            if worker_id == worker_work_unit['worker_id']:
                Db.update_results(work_unit_id, work_unit_results)
                finished_work_units_amount += 1
                if finished_work_units_amount == work_units_amount:
                    time_end = time.time()
                    work_status = Db.WorkStatusNames.finished_work.value
                    results = Db.collect_results()
                    send_to_server('get_results',{"results": results})
                    print(results)
                    print("Made in {} seconds".format(time_end - time_start))
                    #sys.exit(1)
                    #You need  to give time for all the workers to realize their work is done and shut down
            else:
                raise_http_error("I'm a teapot")
        else:
            raise_http_error("I'm a teapot")
    elif worker_log_dict['status'] == 0:
        Db.remove_worker(worker_id)
    elif worker_log_dict['status'] == -1:
        Db.free_work_unit_from_worker(worker_id)

@route('/communication/main_server/get_stats')
def get_stats():
    """
    This function calculates results for the main server to display on the "task_stats" page.
    :return:
    """
    stats = {
        "progress_precent": 100.0*finished_work_units_amount/work_units_amount,
        "results": None if work_status == Db.WorkStatusNames.finished_work.value else Db.collect_results(),
        #If it's already finished, then all the results were already sent to the main server.
         }
    return stats

@route('/communication/main_server/stop_working')
def stop_working():
    sys.exit()


@route('/communication/worker/getexefile/<worker_id>/<requested_exe_name>')
def getexefile(worker_id, requested_exe_name):
    worker_data = identify(worker_id)
    file_dir = handle_path(main_directory + '/' + exe_folder)
    if not requested_exe_name.endswith('.exe'):
        requested_exe_name = requested_exe_name + '.exe'

    #data_to_worker = {'file': static_file(filename, root=file_dir, download=filename)}
    #return package_data(data_to_worker)
    if not os.path.isfile(handle_path(file_dir + '/' + requested_exe_name)):
        print("The server didn't find the file.")
        raise_http_error("Not Found")
    return static_file(requested_exe_name, root=file_dir, download=requested_exe_name)


"""
def getexefile(worker_id, filename):
    identify(worker_id)
    code = read_file(filename, 'exefile')
    code_to_send = {'code': code}
    return package_data(code_to_send)
"""
hostname = socket.gethostname()
IPAddr = socket.gethostbyname(hostname)
print("Server {} of IP {} is ready to go!".format(hostname, IPAddr))

print("http://" + IPAddr + ':' + str(PORT))
#print(connect_to_route('lol').content)
results= [1,2,3,4,5,6,7,8,9]
#send_to_server('get_results',{"results":results})
startworking()
run(host='0.0.0.0', port=PORT)

"""
@route('/communication/worker/signup/<comupter_id>')
def signup(comupter_id):
    
    The worker who communicated to this server for the first time, will get
    :return:
    
    identify(comupter_id , computers)
    new_worker_id = str(id_generator())
    global workers
    workers[new_worker_id] = {}
    workers[new_worker_id]['computer_id'] = comupter_id
    workers[new_worker_id]['status'] = Db.WorkerStatusNames.just_joined.value
    sign_up_data = {"id": new_worker_id}
    return package_data(sign_up_data)
)
"""