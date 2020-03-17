import Calc_farm_database_analyser as Db
import enum


class WorkStatusNames(enum.Enum):
    no_work = 0
    has_work = 1
    finished_work = 2


class WorkUnitStatusNames(enum.Enum):
    untouched = 0
    in_progress = 1
    finished = 2


class WorkerStatusNames(enum.Enum):
    just_joined = 0
    working = 1
    waiting = 2
    crashed = 3


class WorkerServerError(Exception):
    """
    When an error happened in the server's actions or in his communiations with the server
    and the he can't work.
    When it is raise, it will send a negative message to the
    """
    pass


server_database = Db.Database('work_server_database')
tables_code = []

tables_code.append("""
create table workers
(
    worker_id varchar primary key,
    worker_ip varchar,
    worker_status int default {}
);
""".format(WorkerStatusNames.just_joined.value))

tables_code.append("""
create table work_units
(
    work_unit_id integer primary key autoincrement,
    first_num int not null,
    last_num int not null,
    work_unit_status int default {},
    worker_id varchar
        constraint table_name_workers_worker_id_fk
            references workers
);

""".format(WorkUnitStatusNames.untouched.value))

# server_database.reset_table("workers")
#In the funture include a row "Last time alive), witch includes the real time where the
#Maybe even ping to the worker

tables_code.append("""
CREATE TABLE work_unit_results
(
	work_unit_id int
		constraint work_unit_results_pk
			primary key,
	first_num int not null,
    last_num int not null,
	results text not null
)
""")
#I decided to move the data of a work unit from the "Work Units" table to the "Results table",
#because when a work unit is finished, it shouldn't be in the list where the server searches for untouched work units.
#For exmaple, if there are a million work units, and the workers finished computing all of them but one,
#It won't make sense to go over all the 999,999 finished work units, just to get to the last one.

for table_code in tables_code:
    server_database.create_table(table_code, replace_table=True)

#Make sure that the functions to this only gets id's and no full work units or worker id to prevent data from different
#sources.
#You derive all the information from the database to prevent confution and entering wrong information .
#There could be a mistake where the work unit and it's "supposed" assigned worker id, But they could be mismatched
#If you want the worker id, you dervi

def find_worker(worker_id):
    """

    :param worker_id: The id of the worker we want to check.
    :return: Information about the worker. If the worker doesn't exist, it will return None.
    """
    worker_data = server_database.find_specific_record("workers", {"worker_id":worker_id}, return_data=True)
    return worker_data


def insert_worker(worker_details):
    """
    The function inserts a worker into the database.
    :param worker_details: a dictionary with data about the worker that will be written in the "workers" table:
            "worker_id":the id of the worker, "worker_ip": the ip of the computer the comupter is working on.
    """
    if server_database.find_specific_record("workers",{"worker_id":worker_details["worker_id"]}):
        raise WorkerServerError("The user already exsists")
    server_database.dump_data("workers", worker_details)


#def get_worker(worker_id):


def insert_work_unit(work_unit_details):
    """
    The function inserts a work unit into the database.
    :param work_unit_details: data about the work unit that will be written in the "work units" table.
    """

    server_database.dump_data("work_units", work_unit_details)


def get_work_unit(work_unit_id):
    """
    Returns data about a work unit from it's database, based on the work unit's id.
    :param work_unit_id: The id of the work unit.
    :return: Returns data about the work unit. Returns None if it doesn't exist.
    """
    work_unit_data = server_database.find_specific_record("work_units", {"work_unit_id": work_unit_id}, return_data=True)
    return work_unit_data


def get_work_unit_by_worker(worker_id):
    """
    Returns data about a work unit from it's database, based on it worker's id.
    :param worker_id: The id of the worker that was assigned to the that work unit.
    :return: Returns the entire row about the specific work unit. Returns None if it doesn't exist.
    """
    work_unit_data = server_database.find_specific_record("work_units", {"worker_id": worker_id}, return_data=True)
    return work_unit_data


def get_free_work_unit():
    """
    Gets from the database a work unit that wasn't assigned to any worker and isn't worked on.
    :return: a work unit as a dictionary of columns and values
    """

    work_unit_data = server_database.load_data("work_units",
                                               condition="work_unit_status=" + str(WorkUnitStatusNames.untouched.value),
                                               row_num=1)
    #Here I use load data becuase an int doesn't need special treamtment to be encoded
    return work_unit_data


def assign_work_unit(work_unit_id, worker_id):
    """

    :param work_unit_id:
    :param worker_id:
    :return:
    """
    server_database.update_records("work_units",
                                   {"worker_id": worker_id, "work_unit_status": WorkUnitStatusNames.in_progress.value},
                                   condition="work_unit_id=$?", code_args=[work_unit_id])

    server_database.update_records("workers",{"worker_status": WorkerStatusNames.working.value},
                                   condition="worker_id=$?", code_args=[worker_id])


def free_work_unit(work_unit_id):
    """

    :param work_unit:
    :return:
    """
    work_unit = get_work_unit(work_unit_id)
    server_database.update_records("work_units",
                                   {"worker_id": None, "work_unit_status": WorkUnitStatusNames.untouched.value},
                                   condition="work_unit_id=$?", code_args=[work_unit_id])

    worker_id = work_unit['worker_id']
    server_database.update_records("workers", {"worker_status": WorkerStatusNames.waiting.value},
                                   condition="worker_id=$?", code_args=[worker_id])

def free_work_unit_from_worker(worker_id):
    """

    :param worker_id:
    :return:
    """
    work_unit = get_work_unit_by_worker(worker_id)
    if work_unit is not None:
        server_database.update_records("work_units",
                                   {"worker_id": None, "work_unit_status": WorkUnitStatusNames.untouched.value},
                                   condition="work_unit_id=$?", code_args=[work_unit["work_unit_id"]])

        server_database.update_records("workers", {"worker_status": WorkerStatusNames.waiting.value},
                                   condition="worker_id=$?", code_args=[worker_id])


def remove_worker(worker_id):
    free_work_unit_from_worker(worker_id)
    server_database.delete_records("workers","worker_id = $?", [worker_id])


def update_results(work_unit_id, results):
    """

    :param work_unit_id: The ID of a work unit to be transferred to the "Results" table.
    :param results: A list of results from that work unit.
    """

    work_unit = get_work_unit(work_unit_id)
    work_unit_data = {
        "work_unit_id": work_unit_id,
        "first_num": work_unit["first_num"],
        "last_num": work_unit["last_num"],
        "results": results
    }

    server_database.dump_data("work_unit_results", work_unit_data)
    server_database.delete_records("work_units", "work_unit_id=$?", con_args=[work_unit_id])
    server_database.update_records("workers", {"worker_status": WorkerStatusNames.waiting.value},
                                   condition="worker_id=$?", code_args=[work_unit["worker_id"]])



def collect_results():
    """
    Collects all the results from every work_unit to one list.
    :return: a list of all the results, ordered by the work unit id.
    """
    results = []
    finished = False
    work_unit_id = 1
    while not finished:
        results_data = server_database.find_specific_record("work_unit_results",
                                                            {"work_unit_id": work_unit_id}, return_data=True)
        if results_data is None:
            finished = True
        else:
            row_results = results_data["results"]
            if isinstance(row_results, list):
                results += row_results
            elif row_results is not None:
                results.append(results_data)

        work_unit_id += 1

    return results

#server_database.update_records("work_units", {"work_unit_status":WorkUnitStatusNames.in_progress.value})

#print(get_free_work_unit())