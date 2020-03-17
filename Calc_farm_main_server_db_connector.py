import Calc_farm_database_analyser as Db
import os
import enum
import hashlib
import math
from random import choice

class MainServerError(Exception):
    """

    """
    pass


class TaskStatusNames(enum.Enum):
    untouched = 0
    in_progress = 1
    finished = 2


task_status_names_list = ["untouched", "in_progress", "finished"]


class WorkStatusNames(enum.Enum):
    no_work = 0
    has_work = 1
    finished_work = 2

HTTPSTATUSCODES = {"Bad Request": 400,
                   "Unauthorized": 401,
                   "Forbidden": 403,
                   "Not Found": 404,
                   "I'm a teapot": 418,
                   "Internal Server Error": 500
                   }
HTTPSTATUSCODESDECODER = {400: "Bad Request",
                   401: "Unauthorized",
                   403: "Forbidden",
                   404: "Not Found",
                   418: "I'm a teapot",
                   500: "Internal Server Error"
                   }
HTTPSTATUSMESSAGES = {"Bad Request": "The server did not recognise the command",
                      "Unauthorized": "The server doesn't recognise you.",
                      "Forbidden": "You aren't qualified to get access to this service",
                      "Not Found": "The resource you asked for doesn't exist.",
                      "I'm a teapot": "I'm sorry kind sir, I can't offer you tea!",
                      "Internal Server Error": "There was an error in a process inside the server"
                      }


task_form_details = [
    {'form_name': 'task_name', 'form_text': 'Task Name:', 'type': 'text', 'input_type': str,
     'form_text_after': '<p>wronglol</p>:'},
    {'form_name': 'first_num', 'form_text': '<br>number range:', 'type': 'text', 'input_type': int},
    {'form_name': 'last_num', 'form_text': ' - ', 'type': 'text', 'input_type': int}
]

signup_form_details = [
    {
    'form_name': 'user_name', 'form_text': '<p>Enter username:</p>',
     'form_text_after': '<br><p class = "warnings" id="user_name_warning"></p>',
     'type': 'text', 'input_type': str},
    {'form_name': 'password', 'form_text': '<br>Enter password', 'type': 'password', 'input_type': str}
    ]

login_form_details = [
    {'form_name': 'user_name', 'form_text': '<p>Enter username:</p>',
     'form_text_after': '<br><p class = "warnings" id="password_warning"></p>',
     'type': 'text', 'input_type': str},
    {'form_name': 'password', 'form_text': '<br>Enter password', 'type': 'password', 'input_type': str}
    ]

database_handler = Db.Database('Calc_Farm_Main_Server_database')

tables_code = []

tables_code.append("""
create table online_data
(
	user_name varchar not null,
	password varchar not null,
	constraint table_name_pk
		unique (user_name, password)
);
""")

tables_code.append("""
create table sessions
(
	sid varchar not null
		constraint sessions_pk
			primary key,
	username varchar not null
		constraint sessions_online_data_user_name_fk
			references online_data (user_name)
);
""")

tables_code.append("""
create table Tasks
(
	Task_name varchar,
	user_name varchar
		constraint table_name_online_data_user_name_fk
			references online_data (user_name),
	first_num int not null,
	last_num int not null,
	exe_name varchar not null,
	work_force_percentage int,
	Task_conditional varchar,
	    constraint table_name_pk
		    primary key (user_name, Task_name)
);
""")

tables_code.append("""
create table current_tasks
(
	Task_name varchar
		constraint current_tasks_Tasks_Task_name_fk
			references Tasks (Task_name),
	user_name varchar
	    constraint table_name_online_data_user_name_fk
			    references online_data (user_name),
	Task_status int default {},
	server_status int default {},
	work_force_percentage int,
	Task_Connected_workers int default 0,
	server_ip varchar,
	Task_results text
);
""".format(TaskStatusNames.untouched.value, WorkStatusNames.no_work.value))
#Plase do that every time the server's status changes, it will update the main server in "Server_Status
for table_code in tables_code:
    database_handler.create_table(table_code)
    #database_handler.create_table(table_code, replace_table=True)
#For debug perposes, it will replace the tables, change it later to "False"!

def __encode_importent_info(info):
    """
    Encodes importent information such that hackers won't understand.
    :param info: The information you want to encode as a string.
    :param return_string: Weather you want the output to be a normal string(False), or encoded(True)
    :return: the information you inputted encoded as a string of hexadecimals.
    """
    return hashlib.sha256(str(info).encode()).hexdigest()


#There is a problem with this solution, if a hacker gets the original string username and the encryption
# mathod, he can encode it in that mathod and look for the encoded version in the database instead.
#and if he finds the encoded version, then
#When the user is going to log in, he will insert the user_name and password, which will be sent to the server


def create_session(sid, username, prev_sid=None):
    if prev_sid:
        database_handler.delete_records("sessions", "sid=?", [repr(prev_sid)])

    if database_handler.find_specific_record("sessions", {"username": username}):
        database_handler.delete_records("sessions", "username=?", [repr(username)])

    database_handler.dump_data('sessions', {"sid": sid, "username": username})


def delete_session(sid):
    database_handler.delete_records("sessions", "sid=?", [repr(sid)])

def find_user(username, return_data=False):
    return database_handler.find_specific_record("online_data", {"user_name": username},
                                                 return_data=return_data)

def find_user_name_by_password_checking(username, password):
    encoded_suspisoius_password = __encode_importent_info(password)
    user_row = database_handler.find_specific_record("online_data", {"user_name": username,
                                                                     "password": encoded_suspisoius_password},
                                                     return_data=True)
    return user_row

def find_user_name_by_sid(sid):
    user_row = database_handler.find_specific_record("sessions", {"sid": sid}, select_columns=["username"],
                                                 return_data=True)
    if user_row is None:
        return None
    else:
        return user_row["username"]

def insert_user(user_name, password):
    if find_user(user_name):
        raise MainServerError("This user already exists, try using a different one")
    else:
        user_data = {'user_name': user_name, 'password': __encode_importent_info(str(password))}
   # if not __user_exists(encoded_username):
        database_handler.dump_data("online_data", user_data)


def insert_task(user_name, task_data):
    if find_user(user_name):
        task_name = task_data["Task_name"]
        if not database_handler.find_specific_record("current_tasks",{"Task_name": task_name, "user_name": user_name}):
            task_data["user_name"] = user_name
            there_are_normal_tasks = database_handler.check_for_record("Tasks",
                                                            condition="user_name=? and work_force_percentage is null",
                                                                       check_args=[repr(user_name)])

            there_are_percent_tasks = database_handler.check_for_record("Tasks",
                                                        condition="user_name=? and work_force_percentage is not null",
                                                                        check_args=[repr(user_name)])

            if there_are_percent_tasks and "work_force_percentage" in task_data:
                total_percent = database_handler.collect_sql_quarry_result(
                    "select sum(work_force_percentage) from Tasks where user_name=? and work_force_percentage is not null",
                    [repr(user_name)])[0] + task_data["work_force_percentage"]
                if total_percent > 100:
                    raise MainServerError("The percentages add to more then the whole")
                elif total_percent == 100 and there_are_normal_tasks:
                    raise MainServerError("The percentages are too high and don't leave space to normal tasks.")
                elif total_percent < 100 and not there_are_normal_tasks:
                    raise MainServerError("The percentages add to less then the whole")

            database_handler.dump_data("Tasks", task_data)
    else:
        raise MainServerError("The username doesn't exist.")


def start_working_on_a_task(user_name, task_name):
    if not database_handler.find_specific_record("current_tasks", {"Task_name": task_name, "user_name": user_name}):
        task_data = database_handler.find_specific_record("Tasks",
                                                          values={"user_name": user_name, "Task_name": task_name},
                                                          return_data=True)
        if task_data is None:
            raise MainServerError("The task of that user doesn't exist")

        if user_name != task_data["user_name"]:
            raise MainServerError("The username doesn't match the task.")

        database_handler.dump_data("current_tasks",
                                   {"Task_name": task_data["Task_name"], "user_name": user_name,
                                    "work_force_percentage": task_data["work_force_percentage"]})


def cancel_working_on_task(user_name, task_name):
    if database_handler.find_specific_record("current_tasks",{"Task_name": task_name, "user_name": user_name}):
        database_handler.delete_records("current_tasks", "Task_name=:task_name and user_name=:user_name",
                                        con_args={"task_name": repr(task_name), "user_name": repr(user_name)})


def find_task(task_name, user_name, return_task_data=False):
    return database_handler.find_specific_record("Tasks",
                                                      values={"Task_name": task_name,
                                                              "user_name": user_name},
                                                      return_data=return_task_data, row_num=1)


def get_all_tasks_by_user(user_name):
    tasks_row = database_handler.load_data("Tasks", condition="user_name=?", select_columns=["Task_name"], select_args=
    [repr(user_name)], filer_unique_row=False)
    if not tasks_row:
        return None

    return [row["Task_name"] for row in tasks_row]


def get_all_running_tasks_by_user(user_name):
    tasks_row = database_handler.load_data("current_tasks", condition="user_name=?",
                                           select_args=[repr(user_name)], filer_unique_row=False)
    if not tasks_row:
        return None

    return tasks_row


def get_free_tasks(user_name):
    current_task_data = database_handler.find_specific_record("current_tasks",
                                                      values={"user_name": user_name,
                                                              "Task_status": TaskStatusNames.untouched.value},
                                                      return_data=True, row_num=1)

    # Here I use load data becuase an int doesn't need special treamtment to be encoded
    if current_task_data is None:
        return None
    else:
        task_data = find_task(current_task_data["Task_name"], user_name, return_task_data=True)
        if task_data is None:
            raise MainServerError('In "Current Tasks" there is listed a task that does not exist')
        else:
            return task_data


def get_server_ip(task_name, username):
    task_ip = database_handler.find_specific_record("current_tasks",
                                                      values={"user_name": username, "Task_name": task_name},
                                                      select_columns=["server_ip"],
                                                      return_data=True)
    if task_ip is None:
        #raise MainServerError('The task that does not exist.')
        return None
    else:
        return task_ip["server_ip"]

def assign_task(user_name, task_name, work_server_ip):
    """
    Asigns a task to an available work_server_ip
    #get the user name from the wor k server that has the arguments of the user name
    and the name of the task
    :param task_name:
    :param user_name:
    :param work_server_ip:
    :return:
    """

    database_handler.update_records("current_tasks",
                                   {"server_ip": work_server_ip, "Task_status": TaskStatusNames.in_progress.value},
                                   condition="Task_name=$? and user_name=$?", code_args=[task_name, user_name])


def set_results(user_name, work_server_ip, task_results):
    database_handler.update_records("current_tasks",
                                    {"Task_results": task_results, "Task_status": TaskStatusNames.finished.value},
                                    condition="server_ip=$? and user_name=$?", code_args=[work_server_ip, user_name])

def get_results(user_name, task_name):
    results= database_handler.find_specific_record("current_tasks",
                                                 values={"Task_name": task_name,
                                                         "user_name": user_name},
                                                 return_data=True, select_columns=["Task_results"])
    if results is None:
        return None
    else:
        return results["Task_results"]


def free_task(task_name, user_name):
    """

    :param work_unit:
    :return:
    """
    database_handler.update_records("current_tasks",
                                    {"server_ip": None,
                                     "Task_status": TaskStatusNames.untouched.value},
                                    condition="Task_name=$? and user_name=$?", code_args=[task_name, user_name])

"""
def get_number_of_workers(user_name):
    return database_handler.collect_sql_quarry_result(
        "select sum(Task_Connected_workers) from current_tasks where user_name=?", [repr(user_name)])[0]
"""


def assign_worker(user_name):
    priority_current_tasks = database_handler.load_data("current_tasks",
                                                 condition="user_name=? and work_force_percentage is not null"
                                                           " and server_ip is not null",
                                                 select_args=[repr(user_name)],
                                                 order_by_columns=["work_force_percentage"], order_type="DESC",
                                                 filer_unique_row=False)



    normal_current_tasks = database_handler.load_data("current_tasks",
                                                 condition="user_name=? and work_force_percentage is null"
                                                           " and server_ip is not null",
                                                 select_args=[repr(user_name)],
                                                 order_by_columns=["Task_Connected_workers"],
                                                 filer_unique_row=False)

    if normal_current_tasks is None and priority_current_tasks is None:
        return None

    if priority_current_tasks is not None:
        #print(priority_current_tasks)
        total_work_force = database_handler.collect_sql_quarry_result(
            "select sum(Task_Connected_workers) from current_tasks where user_name=?", [repr(user_name)])[0] + 1
        for task in priority_current_tasks:
            percent_from_whole = math.ceil(total_work_force*(task["work_force_percentage"]/100.0))
            if task["Task_Connected_workers"] < percent_from_whole:
                database_handler.update_records("current_tasks",
                                                {"Task_Connected_workers": task["Task_Connected_workers"] + 1},
                                                condition="Task_name=$? and user_name=$?",
                                                code_args=[task["Task_name"],
                                                           user_name])


                worker_task = find_task(task["Task_name"], user_name, return_task_data=True)
                worker_task["server_ip"] = task["server_ip"]
                return worker_task



    minimum_work_force_tasks = [normal_current_tasks[0]]
    minimum_work_force = normal_current_tasks[0]["Task_Connected_workers"]
    for task in normal_current_tasks[1:]:
        if minimum_work_force == task["Task_Connected_workers"]:
            minimum_work_force_tasks.append(task)
        else:
            break

    assigned_task = choice(minimum_work_force_tasks)
    database_handler.update_records("current_tasks",
                                    {"Task_Connected_workers": assigned_task["Task_Connected_workers"] + 1},
                                    condition="Task_name=$? and user_name=$?", code_args=[assigned_task["Task_name"],
                                                                                          user_name])
    worker_task = find_task(assigned_task["Task_name"], user_name, return_task_data=True)
    worker_task["server_ip"] = assigned_task["server_ip"]
    return worker_task


#search join in sql, replace it in the future


code = """
CREATE TABLE rwr
(
	column_1 integer
		constraint rwr_pk
			primary key autoincrement,
	name varchar not null
)

"""

database_handler.create_table(code)
test_data = {'name': 'Gimmie'}


#user_data = {'condition':}
#print(database_handler.collect_sql_quarry_result("select * from table_name where column_2=?;", (5,)))
#print(database_handler.collect_sql_quarry_result("select * from table_name where :condition;", user_data))
#print(database_handler.check_for_record("table_name",'column_1=1'))

"""
insert_user('a', 'b')
insert_user('c', 'd')
insert_task('a', {"Task_name": "prime_range", "first_num": 1, "last_num": 10000, "exe_name": "prime_range"})
insert_task('a', {"Task_name": "goldbach_conjecture", "first_num": 1, "last_num": 10000, "exe_name": "gold",
                  "work_force_percentage":50})
insert_task('a', {"Task_name": "task3", "first_num": 1, "last_num": 10000, "exe_name": "gold",
                  "work_force_percentage":25})
insert_task('a', {"Task_name": "task4", "first_num": 1, "last_num": 10000, "exe_name": "gold",
                  "work_force_percentage":15})
start_working_on_a_task('a', "prime_range")
start_working_on_a_task('a', "goldbach_conjecture")
start_working_on_a_task('a', "task3")
start_working_on_a_task('a', "task4")
"""
def main():

    for table_code in tables_code:
        database_handler.create_table(table_code, replace_table=True)
    insert_user('Default_UserName', '12345')
    insert_user('c', 'd')
    insert_task('Default_UserName', {"Task_name": "prime_range", "first_num": 1, "last_num": 10000, "exe_name": "prime_range"})
    insert_task('Default_UserName', {"Task_name": "goldbach_conjecture", "first_num": 1, "last_num": 10000, "exe_name": "gold",
                      "work_force_percentage": 50})
    insert_task('Default_UserName', {"Task_name": "task3", "first_num": 1, "last_num": 10000, "exe_name": "gold",
                      "work_force_percentage": 25})
    insert_task('Default_UserName', {"Task_name": "task4", "first_num": 1, "last_num": 10000, "exe_name": "gold",
                      "work_force_percentage": 15})
    insert_task('c', {"Task_name": "task5", "first_num": 1, "last_num": 10000, "exe_name": "gold",
                      "work_force_percentage":50})
    insert_task('c', {"Task_name": "task6", "first_num": 1, "last_num": 10000, "exe_name": "gold",
                      "work_force_percentage":50})
    start_working_on_a_task("Default_UserName", "prime_range")
    start_working_on_a_task("c", "task5")
    assign_task("c", "task5", "10.0.0.7")
#insert_task('a', {"Task_name": "task4", "first_num": 1, "last_num": 10000, "exe_name": "gold",
#                  "work_force_percentage":15})

#cancel_working_on_task("a", "task4")

#insert_task('c', {"Task_name": "task5", "first_num": 1, "last_num": 10000, "exe_name": "gold",
                #  "work_force_percentage":50})
#insert_task('c', {"Task_name": "task6", "first_num": 1, "last_num": 10000, "exe_name": "gold",
            #      "work_force_percentage":50})
#print(get_all_tasks_by_user('a'))
#assign_worker('a')
#print(get_number_of_workers('a'))
#print(find_user_name_by_sid('lweR-RGG_uLG5PlbdyCwAw'))
"""

"""

#if __name__ == "__main__":
main()