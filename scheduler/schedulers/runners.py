#
# Copyright (c) 2018 ISP RAS (http://www.ispras.ru)
# Ivannikov Institute for System Programming of the Russian Academy of Sciences
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import math
import utils
from schedulers import SchedulerException


def incmean(prevmean, n, x):
    """Calculate incremental mean"""
    newmean = prevmean + int(round((x - prevmean) / n))
    return newmean


def incsum(prevsum, prevmean, mean, x):
    """Caclulate incremental sum of square deviations"""
    newsum = prevsum + (x - prevmean) * (x - mean)
    return newsum


def devn(cursum, n):
    """Caclulate incremental standart deviation"""
    deviation = int(round(math.sqrt(cursum / n)))
    return deviation


class Runner:
    """Class provide general scheduler API."""

    def __init__(self, conf, logger, work_dir, server):
        """
        Get configuration and prepare working directory.

        :param conf: Dictionary with relevant configuration.
        :param logger: Logger object.
        :param work_dir: PAth to the working directory.
        :param server: Session object.
        """
        self.conf = conf
        self.logger = logger
        self.work_dir = work_dir
        self.server = server
        self.init()
        utils.kv_clear_solutions(self.logger, self.scheduler_type())

    @staticmethod
    def scheduler_type():
        """Return type of the scheduler: 'VerifierCloud' or 'Klever'."""
        raise NotImplementedError

    def is_solving(self, item):
        """
        Check that task or job has been started.

        :param item: Dictionary.
        :return: Bool
        """
        return 'future' in item

    def init(self):
        """
        Initialize scheduler completely. This method should be called both at constructing stage and scheduler
        reinitialization. Thus, all object attribute should be cleaned up and set as it is a newly created object.
        """
        return

    def schedule(self, pending_tasks, pending_jobs):
        """
        Get a list of new tasks which can be launched during current scheduler iteration. All pending jobs and tasks
        should be sorted reducing the priority to the end. Each task and job in arguments are dictionaries with full
        configuration or description.

        :param pending_tasks: List with all pending tasks.
        :param pending_jobs: List with all pending jobs.
        :return: List with identifiers of pending tasks to launch and list woth identifiers of jobs to launch.
        """
        # Runners must implement the method
        raise NotImplementedError

    def prepare_task(self, identifier, item):
        """
        Prepare the task before rescheduling. This method is public and cannot raise any unexpected exceptions and can
        do rescheduling. This method is public and cannot raise any unexpected exceptions and can do
        rescheduling.

        :param identifier: Verification task identifier.
        :param item: Dictionary with task description.
        """
        self.logger.debug("Prepare new task {} before launching".format(identifier))
        try:
            # Add missing restrictions
            self._prepare_task(identifier, item["description"])
        except SchedulerException as err:
            self.logger.error("Cannot prepare task {} for submission: {!r}".format(identifier, err))
            item["status"] = "ERROR"
            item["error"] = err

    def _prepare_task(self, identifier, description):
        """
        Prepare a working directory before starting the solution.

        :param identifier: Verification task identifier.
        :param description: Dictionary with task description.
        :raise SchedulerException: If a task cannot be scheduled or preparation failed.
        """
        # Runners must implement the method
        raise NotImplementedError

    def prepare_job(self, identifier, item):
        """
        Prepare job before the solution. This method is public and cannot raise any unexpected exceptions and can do
        rescheduling.

        :param identifier: Verification job identifier.
        :param item: Dictionary with job description.
        """
        # Prepare jobs before launching
        self.logger.debug("Prepare new job {} before launching".format(identifier))
        try:
            self._prepare_job(identifier, item["configuration"])
        except SchedulerException as err:
            self.logger.error("Cannot prepare job {} for submission: {!r}".format(identifier, err))
            item["status"] = "ERROR"
            item["error"] = err

    def _prepare_job(self, identifier, configuration):
        """
        Prepare a working directory before starting the solution.

        :param identifier: Verification job identifier.
        :param configuration: Job configuration.
        :raise SchedulerException: If a job cannot be scheduled or preparation failed.
        """
        # Runners must implement the method
        raise NotImplementedError

    def solve_task(self, identifier, item):
        """
        Solve the task. This method is public and cannot raise any unexpected exceptions and can do rescheduling.

        :param identifier: Verification task identifier.
        :param item: Verification task description dictionary.
        :return: Bool.
        """
        try:
            item["future"] = self._solve_task(identifier, item["description"], item["user"], item["password"])
            item["status"] = "PROCESSING"
            return True
        except SchedulerException as err:
            item.setdefault("attempts", 0)
            item["attempts"] += 1

            if item["attempts"] > 2:
                msg = "Cannot solve task {}: {!r}".format(identifier, err)
                self.logger.warning(msg)
                item.update({"status": "ERROR", "error": msg})
                return True
            return False

    def _solve_task(self, identifier, description, user, password):
        """
        Solve given verification task.

        :param identifier: Verification task identifier.
        :param description: Verification task description dictionary.
        :param user: User name.
        :param password: Password.
        :return: Return Future object.
        """
        # Runners must implement the method
        raise NotImplementedError

    def solve_job(self, identifier, item):
        """
        Solve given verification job. This method is public and cannot raise any unexpected exceptions and can do
        rescheduling.

        :param identifier: Job identifier.
        :param item: Job descitption.
        :return: Bool.
        """
        try:
            item["future"] = self._solve_job(identifier, item)
            return True
        except SchedulerException as err:
            item.setdefault("attempts", 0)
            item["attempts"] += 1

            if item["attempts"] > 2:
                msg = "Cannot solve job {}: {!r}".format(identifier, err)
                self.logger.warning(msg)
                item.update({"status": "ERROR", "error": msg})
                return True
            return False

    def _solve_job(self, identifier, configuration):
        """
        Solve given verification job.

        :param identifier: Job identifier.
        :param configuration: Job configuration.
        :return: Return Future object.
        """
        # Runners must implement the method
        raise NotImplementedError

    def flush(self):
        """Start solution explicitly of all recently submitted tasks."""
        return

    def process_task_result(self, identifier, item):
        """
        Process result and send results to the server.

        :param identifier: Task identifier string.
        :param item: Verification task description dictionary.
        :return: Bool if status of the job has changed.
        """
        if item["future"].done():
            try:
                item["status"] = self._process_task_result(identifier, item["future"], item["description"])
                self.logger.debug("Task {} new status is {!r}".format(identifier, item["status"]))
                assert item["status"] in ["FINISHED", "ERROR"]
            except SchedulerException as err:
                msg = "Task failed {}: {!r}".format(identifier, err)
                self.logger.warning(msg)
                item.update({"status": "ERROR", "error": msg})
            finally:
                utils.kv_clear_solutions(self.logger, self.scheduler_type(), identifier)
                del item["future"]
                return True
        else:
            return False
    
    def _process_task_result(self, identifier, future, description):
        """
        Process result and send results to the server.

        :param identifier: Task identifier string.
        :param future: Future object.
        :param description: Verification task description dictionary.
        :return: status of the task after solution: FINISHED.
        :raise SchedulerException: in case of ERROR status.
        """
        # Runners must implement the method
        raise NotImplementedError

    def process_job_result(self, identifier, item, task_items):
        """
        Process future object status and send results to the server.

        :param identifier: Job identifier string.
        :param item: Verification job description dictionary.
        :param task_items: Verification tasks description to cancel them if necessary.
        :return: Bool if status of the job has changed.
        """
        if item.get("future") and item["future"].done():
            try:
                item["status"] = self._process_job_result(identifier, item["future"])
                self.logger.debug("Job {} new status is {!r}".format(identifier, item["status"]))
                assert item["status"] in ["FINISHED", "ERROR"]
            except SchedulerException as err:
                msg = "Job failed {}: {!r}".format(identifier, err)
                self.logger.warning(msg)
                item.update({"status": "ERROR", "error": msg})

                # Cancel tasks
                for task in task_items:
                    self.cancel_task(task["id"], task)
            finally:
                del item["future"]
                return True
        else:
            return False

    def _process_job_result(self, identifier, future):
        """
        Process future object status and send results to the server.

        :param identifier: Job identifier string.
        :param future: Future object.
        :return: status of the job after solution: FINISHED.
        :raise SchedulerException: in case of ERROR status.
        """
        # Runners must implement the method
        raise NotImplementedError

    def cancel_job(self, identifier, item, task_items):
        """
        Stop the job solution.

        :param identifier: Job identifier string.
        :param item: Verification job description dictionary.
        :param task_items: Verification tasks description to cancel them if necessary.
        """
        try:
            if item.get("future") and not item["future"].cancel():
                item["status"] = self._cancel_job(identifier, item["future"])
                assert item["status"] in ["FINISHED", "ERROR"]
            else:
                item["status"] = "ERROR"
                item["error"] = "Task has been cancelled before execution"
            self.logger.debug("Job {} new status is {!r}".format(identifier, item["status"]))
        except SchedulerException as err:
            self.logger.error("Job {} has failed: {!r}".format(identifier, err))
            item["status"] = "ERROR"
            item["error"] = err
        finally:
            # Cancel tasks
            for task in task_items:
                self.cancel_task(task["id"], task)
            if "future" in item:
                del item["future"]

    def _cancel_job(self, identifier, future):
        """
        Stop the job solution.

        :param identifier: Verification job ID.
        :param future: Future object.
        :return: Status of the task after solution: FINISHED. Rise SchedulerException in case of ERROR status.
        :raise SchedulerException: In case of exception occured in future task.
        """
        # Runners must implement the method
        raise NotImplementedError

    def cancel_task(self, identifier, item):
        """
        Stop the task solution.

        :param identifier: Verification task ID.
        :param item: Task description.
        """
        try:
            if item.get("future") and not item["future"].cancel():
                item["status"] = self._cancel_task(identifier, item["future"])
                self.logger.debug("Cancelled task {} finished with status: {!r}".format(identifier, item["status"]))
                assert item["status"] in ["FINISHED", "ERROR"]
            else:
                item["status"] = "ERROR"
                item["error"] = "Task has been cancelled before execution"
            self.logger.debug("Task {} new status is {!r}".format(identifier, item["status"]))
        except SchedulerException as err:
            self.logger.error("Cannot process results of task {}: {!r}".format(identifier, err))
            item["status"] = "ERROR"
            item["error"] = err
        finally:
            if "future" in item:
                del item["future"]

    def _cancel_task(self, identifier, future):
        """
        Stop the task solution.

        :param identifier: Verification task ID.
        :param future: Future object.
        :return: Status of the task after solution: FINISHED. Rise SchedulerException in case of ERROR status.
        :raise SchedulerException: In case of exception occured in future task.
        """
        # Runners must implement the method
        raise NotImplementedError

    def add_job_progress(self, identifier, item, progress):
        """
        Save information about the progress if necessary.

        :param identifier: Job identifier string.
        :param item: Verification job description dictionary.
        :param progress: Information about the job progress.
        """
        return

    def terminate(self):
        """Abort solution of all running tasks and any other actions before termination."""
        utils.kv_clear_solutions(self.logger, self.scheduler_type())
        return

    def update_nodes(self, wait_controller=False):
        """
        Update statuses and configurations of available nodes and push them to the server.

        :param wait_controller: Ignore KV fails until it become working.
        :return: Return True if nothing has changes.
        """
        return True

    def update_tools(self):
        """Generate a dictionary with available verification tools and push it to the server."""
        return


class Speculative(Runner):
    """This runner collects statistics and adjust memory limits to run more tasks."""

    def init(self):
        """
        Initialize scheduler completely. This method should be called both at constructing stage and scheduler
        reinitialization. Thus, all object attribute should be cleaned up and set as it is a newly created object.
        """
        super(Speculative, self).init()
        # Timout tasks
        self._problematic = dict()
        # Data about job tasks
        self._jdata = dict()

    def prepare_task(self, identifier, item):
        """
        Prepare the task before rescheduling. This method is public and cannot raise any unexpected exceptions and can
        do rescheduling. This method is public and cannot raise any unexpected exceptions and can do
        rescheduling.

        :param identifier: Verification task identifier.
        :param item: Dictionary with task description.
        """
        if item["description"]["job id"] in self._jdata:
            limits, speculative = \
                self._resource_limitations(item["description"]["job id"], item["description"]["solution class"],
                                           identifier, item["description"]["resource limits"])
            item["description"]["resource limits"] = limits
            item["description"]["speculative"] = speculative
        super(Speculative, self).prepare_task(identifier, item)

    def solve_job(self, identifier, item):
        """
        Solve given verification job. This method is public and cannot raise any unexpected exceptions and can do
        rescheduling.

        :param identifier: Job identifier.
        :param item: Job descitption.
        :return: Bool.
        """
        successful = super(Speculative, self).solve_job(identifier, item)
        if successful:
            jd = self._track_job(identifier)
            jd["QoS limit"] = dict(item['configuration']['task resource limits'])
        return successful

    def process_task_result(self, identifier, item):
        """
        Process result and send results to the server.

        :param identifier: Task identifier string.
        :param item: Verification task description dictionary.
        :return: Bool if status of the job has changed.
        """
        # Get solution in advance before it is cleaned
        if item["future"].done():
            solution = utils.kv_get_solution(self.logger, self.scheduler_type(), identifier)
        else:
            solution = False
        status = super(Speculative, self).process_task_result(identifier, item)
        if status and solution:
            solved = self._add_solution(item["description"]["job id"], item["description"]["solution class"],
                                        identifier, solution)
            if not solved:
                # We need to prepare task again to set new resource limitations to configuration files and solve it
                # once again
                self.prepare_task(identifier, item)
                self.logger.info("Reschedule task {} of category {!r} due to underapproximated memory limit".
                                 format(identifier, item["description"]["solution class"]))
                item["status"] = "PENDING"
                item["rescheduled"] = True
        elif status and not solution:
            self.logger.info('Missing decision results for task {}:{}'.
                             format(item["description"]["solution class"], identifier))
            self._del_task(item["description"]["job id"], item["description"]["solution class"], identifier)
        return status

    def process_job_result(self, identifier, item, task_items):
        """
        Process future object status and send results to the server.

        :param identifier: Job identifier string.
        :param item: Verification job description dictionary.
        :param task_items: Verification tasks description to cancel them if necessary.
        :return: Bool if status of the job has changed.
        """
        status = super(Speculative, self).process_job_result(identifier, item, task_items)
        if status:
            # Add log and asserts
            jd = self._track_job(identifier)
            if sum([len([jd["limits"][att]["tasks"] for att in jd["limits"]])]) > 0:
                self.logger.debug("Job {} max task number was given as {} and solved successfully {}".
                                  format(identifier, jd.get("total tasks", 0), jd.get("solved", 0)))
                for att, attd in ((a, d) for a, d in jd["limits"].items() if d.get('statistics') is not None):
                    self.logger.info(
                        "Task category {!r} statistics:\n\tsolved: {}\n\tmean memory consumption: {}B\n\t"
                        "memory consumption deviation: {}B\n\tmean CPU time consumption: {}s\n\t"
                        "CPU time consumption deviation: {}s".
                        format(att, attd["statistics"].get("number", 0), attd["statistics"].get("mean mem", 0),
                               attd["statistics"].get("memdev", 0), int(attd["statistics"].get("mean time", 0) / 1000),
                               int(attd["statistics"].get("timedev", 0)) / 1000))

            self.del_job(identifier)
        return status

    def cancel_job(self, identifier, item, task_items):
        """
        Stop the job solution.

        :param identifier: Verification job ID.
        :param item: Verification job description dictionary.
        :param task_items: Verification tasks description to cancel them if necessary.
        """
        super(Speculative, self).cancel_job(identifier, item, task_items)
        self.del_job(identifier)

    def cancel_task(self, identifier, item):
        """
        Stop the task solution.

        :param identifier: Verification task ID.
        :param item: Task description.
        """
        super(Speculative, self).cancel_task(identifier, item)
        if self._is_there(item["description"]["job id"], item["description"]["solution class"], identifier):
            self._del_task(item["description"]["job id"], item["description"]["solution class"], identifier)

    def terminate(self):
        """Abort solution of all running tasks and any other actions before termination."""
        super(Speculative, self).terminate()
        # Clean data
        self._problematic = dict()
        self._jdata = dict()

    def add_job_progress(self, identifier, item, progress):
        """
        Save information about the progress if necessary.

        :param identifier: Job identifier string.
        :param item: Verification job description dictionary.
        :param progress: Information about the job progress.
        """
        super(Speculative, self).add_job_progress(identifier, item, progress)
        if progress.get('total tasks to be generated', None):
            jd = self._track_job(identifier)
            jd['total tasks'] = progress['total tasks to be generated']

    def _is_there(self, job_identifier, attribute, identifier):
        """
        Check that the task if already tracked as a time or memory limit.

        :param job_identifier: Job identifier.
        :param attribute: Attribute given to the job to classify it.
        :param identifier: Identifier of the task.
        :return: True if it is a known limit task.
        """

        if job_identifier in self._jdata and attribute in self._jdata[job_identifier]["limits"] and \
                identifier in self._jdata[job_identifier]["limits"][attribute]["tasks"] and \
                self._jdata[job_identifier]["limits"][attribute]["tasks"][identifier]["status"] in \
                ('OUT OF MEMORY', 'TIMEOUT'):
            return True
        return False

    def _is_there_or_init(self, job_identifier, attribute, identifier):
        """
        Check that the task if already tracked as a time or memory limit. If not create a new description for the task
        as it is a limit.

        :param job_identifier: Job identifier.
        :param attribute: Attribute given to the job to classify it.
        :param identifier: Identifier of the task.
        :return: Description of the task.
        """
        jd = self._track_job(job_identifier)
        attd = jd["limits"].setdefault(attribute,
                                       {
                                           "tasks": dict(),
                                           "statistics": None
                                       })
        task = attd["tasks"].setdefault(identifier, {"limitation": dict(), "status": None})
        return task

    def _del_task(self, job_identifier, attribute, identifier):
        """
        Delete task. This means that it is either solved or failed.

        :param job_identifier: Job identifier.
        :param attribute: Attribute given to the job to classify it.
        :param identifier: Identifier of the task.
        :return: None
        """
        job = self._track_job(job_identifier)
        if attribute in job["limits"]:
            del job["limits"][attribute]["tasks"][identifier]

    def _track_job(self, job_identifier):
        """
        Start tracking the job.

        :param job_identifier: Job identifier.
        :return: Job solutions description.
        """
        return self._jdata.setdefault(job_identifier,
                                      {
                                          "limits": dict(),
                                          "total tasks": None,
                                          "QoS limit": None,
                                          "solved": 0
                                      })

    def del_job(self, job_identifier):
        """
        Stop tracking the job.

        :param job_identifier: job identifier.
        :return: None
        """
        if job_identifier in self._jdata:
            del self._jdata[job_identifier]

    def _resource_limitations(self, job_identifier, attribute, identifier, job_limitations):
        """
        :param job_identifier: Job identifier.
        :param attribute: Attribute given to the job to classify it.
        :param identifier: Identifier of the task.
        :return: New resource limitations.
        """
        # First set QoS limit
        job = self._track_job(job_identifier)
        qos = job.get("QoS limit")
        assert qos is not None
        assert job_limitations is not None

        # Start tracking the element
        element = self._is_there_or_init(job_identifier, attribute, identifier)
        limits = job_limitations

        # Check do we have some statistics already
        speculative = False
        if limits.get('memory size', 0) > 0 and \
                ((limits.get('CPU time') and limits['CPU time'] <= qos['CPU time']) or
                 not limits.get('CPU time')) and not self._is_there(job_identifier, attribute, identifier) and \
                job.get("total tasks", 0) and job["solved"] > (0.1 * job.get("total tasks")) and \
                job["limits"][attribute]["statistics"] and job["limits"][attribute]["statistics"]["number"] > 5:
            statistics = job["limits"][attribute]["statistics"]
            limits['memory size'] = statistics['mean mem'] + 2*statistics['memdev']
            if limits['memory size'] < qos['memory size']:
                self.logger.debug("Issue less memory limit for for {}:{}: {}B".
                                  format(attribute, identifier, limits['memory size']))
                speculative = True
            else:
                limits = dict(qos)
        elif self._is_there(job_identifier, attribute, identifier):
            self.logger.debug("Issue given limit for {}:{}".format(attribute, identifier))
            limits = dict(qos)

        element["limitation"] = limits
        return limits, speculative

    def _add_solution(self, job_identifier, attribute, identifier, solution):
        """
        Save solution and return is this solution is final or not.

        :param job_identifier: Job identifier.
        :param attribute: Attribute given to the job to classify it.
        :param identifier: Identifier of the task.
        :param solution: Data from the task solution.
        :return: True if task is solved.
        """
        status = solution["status"]
        resources = solution["resources"]
        job = self._track_job(job_identifier)
        element = self._is_there_or_init(job_identifier, attribute, identifier)
        element["status"] = status

        # Check that it is an error from scheduler
        if resources:
            self.logger.debug("Task {}:{} finished".format(attribute, identifier))
            lim = element["limitation"]
            qos = job["QoS limit"]
            job["solved"] += 1
            self.logger.debug(
                "Task {} from category {!r} solved with status {!r} and required {}B of memory and {}s of CPU time".
                format(identifier, attribute, status, resources['memory size'], int(resources['CPU time'] / 1000)))
            if not job["limits"][attribute]["statistics"]:
                job["limits"][attribute]["statistics"] = {
                    'mean mem': resources['memory size'],
                    'memsum': 0,
                    'memdev': 0,
                    'mean time': resources['CPU time'],
                    'timesum': 0,
                    'timedev': 0,
                    'number': 1
                }
            else:
                statistics = job["limits"][attribute]["statistics"]
                statistics['number'] += 1
                # First save data for CPU
                newmean = incmean(statistics['mean time'], statistics['number'], resources['CPU time'])
                newsum = incsum(statistics['timesum'], statistics['mean time'], newmean, resources['CPU time'])
                timedev = devn(newsum, statistics['number'])
                statistics.update({'mean time': newmean, 'timesum': newsum, 'timedev': timedev})

                # Then memory
                newmean = incmean(statistics['mean mem'], statistics['number'], resources['memory size'])
                newsum = incsum(statistics['memsum'], statistics['mean mem'], newmean, resources['memory size'])
                memdev = devn(newsum, statistics['number'])
                statistics.update({'mean mem': newmean, 'memsum': newsum, 'memdev': memdev})

            if status in ('OUT OF MEMORY', 'TIMEOUT') and lim and \
                    (lim.get('memory size', 0) < qos.get('memory size', 0)) or \
                    (lim.get('CPU time', 0) < qos.get('CPU time', 0)):
                return False

        self._del_task(job_identifier, attribute, identifier)
        return True
