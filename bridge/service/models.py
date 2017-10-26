#
# Copyright (c) 2014-2016 ISPRAS (http://www.ispras.ru)
# Institute for System Programming of the Russian Academy of Sciences
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

from django.db import models
from django.db.models.signals import pre_delete, post_init
from django.dispatch.dispatcher import receiver
from django.contrib.auth.models import User
from bridge.vars import PRIORITY, NODE_STATUS, TASK_STATUS, SCHEDULER_STATUS, SCHEDULER_TYPE
from bridge.utils import RemoveFilesBeforeDelete
from jobs.models import Job

FILE_DIR = 'Service'


class Scheduler(models.Model):
    type = models.CharField(max_length=1, choices=SCHEDULER_TYPE)
    status = models.CharField(max_length=12, choices=SCHEDULER_STATUS, default='AILING')

    class Meta:
        db_table = 'scheduler'


class VerificationTool(models.Model):
    scheduler = models.ForeignKey(Scheduler)
    name = models.CharField(max_length=128)
    version = models.CharField(max_length=128)

    class Meta:
        db_table = 'verification_tool'


class SchedulerUser(models.Model):
    user = models.OneToOneField(User)
    login = models.CharField(max_length=128)
    password = models.CharField(max_length=128)

    class Meta:
        db_table = 'scheduler_user'


class NodesConfiguration(models.Model):
    cpu = models.CharField(max_length=128)
    cores = models.PositiveSmallIntegerField()
    ram = models.BigIntegerField()
    memory = models.BigIntegerField()

    class Meta:
        db_table = 'nodes_configuration'


class Workload(models.Model):
    jobs = models.PositiveIntegerField()
    tasks = models.PositiveIntegerField()
    cores = models.PositiveSmallIntegerField()
    ram = models.BigIntegerField()
    memory = models.BigIntegerField()
    for_tasks = models.BooleanField()
    for_jobs = models.BooleanField()

    class Meta:
        db_table = 'workload'


class Node(models.Model):
    config = models.ForeignKey(NodesConfiguration)
    status = models.CharField(max_length=13, choices=NODE_STATUS)
    hostname = models.CharField(max_length=128)
    workload = models.OneToOneField(Workload, null=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        db_table = 'node'


@receiver(pre_delete, sender=Node)
def node_delete_signal(**kwargs):
    node = kwargs['instance']
    if node.workload:
        node.workload.delete()


class SolvingProgress(models.Model):
    job = models.OneToOneField(Job)
    priority = models.CharField(max_length=6, choices=PRIORITY)
    scheduler = models.ForeignKey(Scheduler)
    start_date = models.DateTimeField(null=True)
    finish_date = models.DateTimeField(null=True)
    tasks_total = models.PositiveIntegerField(default=0)
    tasks_pending = models.PositiveIntegerField(default=0)
    tasks_processing = models.PositiveIntegerField(default=0)
    tasks_finished = models.PositiveIntegerField(default=0)
    tasks_error = models.PositiveIntegerField(default=0)
    tasks_cancelled = models.PositiveIntegerField(default=0)
    solutions = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=1024, null=True)
    configuration = models.BinaryField()
    fake = models.BooleanField(default=False)
    local_average_time = models.PositiveIntegerField(default=0)
    global_average_time = models.PositiveIntegerField(default=0)
    estimated_total_tasks = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'solving_progress'


@receiver(pre_delete, sender=SolvingProgress)
def progress_delete_signal(**kwargs):
    RemoveFilesBeforeDelete(kwargs['instance'])


@receiver(post_init, sender=SolvingProgress)
def get_progress_configuration(**kwargs):
    progress = kwargs['instance']
    if not isinstance(progress.configuration, bytes):
        progress.configuration = progress.configuration.tobytes()


class Task(models.Model):
    progress = models.ForeignKey(SolvingProgress)
    status = models.CharField(max_length=10, choices=TASK_STATUS, default='PENDING')
    error = models.CharField(max_length=1024, null=True)
    description = models.BinaryField()
    archname = models.CharField(max_length=256)
    archive = models.FileField(upload_to=FILE_DIR, null=False)

    class Meta:
        db_table = 'task'


@receiver(post_init, sender=Task)
def get_task_description(**kwargs):
    task = kwargs['instance']
    if not isinstance(task.description, bytes):
        task.description = task.description.tobytes()


@receiver(pre_delete, sender=Task)
def task_delete_signal(**kwargs):
    RemoveFilesBeforeDelete(kwargs['instance'])


class Solution(models.Model):
    task = models.OneToOneField(Task)
    description = models.BinaryField()
    archname = models.CharField(max_length=256)
    archive = models.FileField(upload_to=FILE_DIR, null=False)

    class Meta:
        db_table = 'solution'


@receiver(post_init, sender=Solution)
def get_solution_description(**kwargs):
    solution = kwargs['instance']
    if not isinstance(solution.description, bytes):
        solution.description = solution.description.tobytes()


@receiver(pre_delete, sender=Solution)
def solution_delete_signal(**kwargs):
    solution = kwargs['instance']
    storage, path = solution.archive.storage, solution.archive.path
    try:
        storage.delete(path)
    except PermissionError:
        pass
