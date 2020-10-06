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

import json
import mimetypes
import os
from wsgiref.util import FileWrapper

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils.translation import activate

import service.utils
from bridge.utils import logger
from bridge.vars import USER_ROLES, UNKNOWN_ERROR, TASK_STATUS, PRIORITY, JOB_STATUS
from jobs.models import Job
from jobs.utils import change_job_status
from service.models import Scheduler, SolvingProgress, Task, VerificationTool, NodesConfiguration, SchedulerUser, \
    Workload
from service.test import TEST_NODES_DATA, TEST_TOOLS_DATA, TEST_JSON
from tools.profiling import unparallel_group

DEFAULT_WVO_LANG = 'EN'


@unparallel_group([SolvingProgress])
def schedule_task(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if 'job id' not in request.session:
        return JsonResponse({'error': 'Session does not have job id'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Just POST requests are supported'})
    if 'description' not in request.POST:
        return JsonResponse({'error': 'Task description is not specified'})
    archive = None
    for f in request.FILES.getlist('file'):
        archive = f
    if archive is None:
        return JsonResponse({'error': 'The task archive was not got'})
    try:
        res = service.utils.ScheduleTask(request.session['job id'], request.POST['description'], archive)
    except service.utils.NotAnError as e:
        logger.info(str(e))
        return JsonResponse({'error': str(e)})
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': str(e)})
    return JsonResponse({'task id': res.task_id})


@unparallel_group([])
def get_tasks_statuses(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Just POST requests are supported'})
    if 'tasks' not in request.POST:
        return JsonResponse({'error': 'Tasks identifiers are not specified'})
    try:
        res = service.utils.GetTasksStatuses(request.POST['tasks'])
    except service.utils.NotAnError as e:
        logger.info(str(e))
        return JsonResponse({'error': str(e)})
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': str(e)})
    return JsonResponse({'tasks statuses': res.statuses})


@unparallel_group([])
def download_solution(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Just POST requests are supported'})
    if 'task id' not in request.POST:
        return JsonResponse({'error': 'Task identifier is not specified'})

    try:
        res = service.utils.GetSolution(request.POST['task id'])
    except service.utils.NotAnError as e:
        logger.info(str(e))
        return JsonResponse({'error': str(e)})
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': str(e)})
    if res.task.status == TASK_STATUS[3][0]:
        return JsonResponse({'task error': res.task.error})
    mimetype = mimetypes.guess_type(os.path.basename(res.solution.archname))[0]
    response = StreamingHttpResponse(FileWrapper(res.solution.archive, 8192), content_type=mimetype)
    response['Content-Length'] = len(res.solution.archive)
    response['Content-Disposition'] = 'attachment; filename="%s"' % res.solution.archname
    return response


@unparallel_group([Task])
def remove_task(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Just POST requests are supported'})
    if 'task id' not in request.POST:
        return JsonResponse({'error': 'Task identifier is not specified'})
    try:
        service.utils.RemoveTask(request.POST['task id'])
    except service.utils.NotAnError as e:
        logger.info(str(e))
        return JsonResponse({'error': str(e)})
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': str(e)})
    return JsonResponse({})


@unparallel_group([SolvingProgress])
def cancel_task(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Just POST requests are supported'})
    if 'task id' not in request.POST:
        return JsonResponse({'error': 'Task identifier is not specified'})
    try:
        service.utils.CancelTask(request.POST['task id'])
    except service.utils.NotAnError as e:
        logger.info(str(e))
        return JsonResponse({'error': str(e)})
    except Exception as e:
        return JsonResponse({'error': str(e)})
    return JsonResponse({})


@unparallel_group([Job])
def get_jobs_and_tasks(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if 'scheduler' not in request.session:
        return JsonResponse({'error': 'The scheduler was not found in session'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported'})
    if 'jobs and tasks status' not in request.POST:
        return JsonResponse({'error': 'Tasks data is required'})
    try:
        jobs_and_tasks = service.utils.GetTasks(
            request.session['scheduler'], request.POST['jobs and tasks status']).newtasks
    except service.utils.ServiceError as e:
        # TODO: email notification
        return JsonResponse({'error': str(e)})
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': 'Unknown error'})
    return JsonResponse({'jobs and tasks status': jobs_and_tasks})


@unparallel_group([])
def download_task(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Just POST requests are supported'})
    if 'task id' not in request.POST:
        return JsonResponse({'error': 'Task identifier is not specified'})

    try:
        res = service.utils.GetTaskData(request.POST['task id'])
    except service.utils.NotAnError as e:
        logger.info(str(e))
        return JsonResponse({'error': str(e)})
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': str(e)})

    mimetype = mimetypes.guess_type(os.path.basename(res.task.archname))[0]
    response = StreamingHttpResponse(FileWrapper(res.task.archive, 8192), content_type=mimetype)
    response['Content-Length'] = len(res.task.archive)
    response['Content-Disposition'] = 'attachment; filename="%s"' % res.task.archname
    return response


@unparallel_group([SolvingProgress])
def upload_solution(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Just POST requests are supported'})
    if 'task id' not in request.POST:
        return JsonResponse({'error': 'Task identifier is not specified'})
    if 'description' not in request.POST:
        return JsonResponse({'error': 'Description is not specified'})

    archive = None
    for f in request.FILES.getlist('file'):
        archive = f
    if archive is None:
        return JsonResponse({'error': 'The solution archive was not got'})
    try:
        service.utils.SaveSolution(request.POST['task id'], archive, request.POST['description'])
    except service.utils.NotAnError as e:
        logger.info(str(e))
        return JsonResponse({'error': str(e)})
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': str(e)})
    return JsonResponse({})


@unparallel_group([NodesConfiguration, Workload])
def update_nodes(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Just POST requests are supported'})
    if 'nodes data' not in request.POST:
        return JsonResponse({'error': 'Nodes data is not specified'})

    try:
        service.utils.SetNodes(request.POST['nodes data'])
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': str(e)})
    return JsonResponse({})


@unparallel_group([VerificationTool])
def update_tools(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in {USER_ROLES[2][0], USER_ROLES[4][0]}:
        return JsonResponse({'error': 'No access'})
    if 'scheduler' not in request.session:
        return JsonResponse({'error': 'The scheduler was not found in session'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported'})
    if 'tools data' not in request.POST:
        return JsonResponse({'error': 'Tools data is not specified'})
    try:
        service.utils.UpdateTools(request.session['scheduler'], request.POST['tools data'])
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': str(e)})
    return JsonResponse({})


@unparallel_group([Scheduler, Job])
def set_schedulers_status(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported'})
    if 'statuses' not in request.POST:
        return JsonResponse({'error': 'Statuses were not got'})
    try:
        service.utils.SetSchedulersStatus(request.POST['statuses'])
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': str(e)})
    return JsonResponse({})


@login_required
@unparallel_group([NodesConfiguration, Workload])
def schedulers_info(request):
    activate(request.user.extended.language)
    return render(request, 'service/scheduler.html', {
        'schedulers': Scheduler.objects.all(), 'data': service.utils.NodesData()
    })


@login_required
@unparallel_group([NodesConfiguration, Workload])
def launcher_view(request, pk=""):
    if request.user.extended.role not in [USER_ROLES[1][0], USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    activate(request.user.extended.language)
    return render(request, 'service/launcher.html', {'data': service.utils.LauncherData(job_id=pk)})


# @login_required
def wvo_view(request):
    activate(DEFAULT_WVO_LANG)
    return render(request, 'service/wvo.html', {})


# @login_required
def wv_view(request, id):
    activate(DEFAULT_WVO_LANG)
    return render(request, 'service/wv.html', {'data': service.utils.get_wvo_content(id)})


# @login_required
@unparallel_group([NodesConfiguration, Workload])
def visualize_witness(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported'})
    wvo = service.utils.VisualizeWitness(request)
    if wvo.error:
        return JsonResponse({'error': wvo.error})
    return JsonResponse({'id': wvo.id})


@login_required
@unparallel_group([NodesConfiguration, Workload])
def get_config(request, file):
    if request.user.extended.role not in [USER_ROLES[1][0], USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    data = service.utils.LauncherData(is_full=True).preset_configs.get(file)
    return JsonResponse({'config': data})


@login_required
def test(request):
    return render(request, 'service/test.html', {
        'priorities': PRIORITY,
        'jobs': Job.objects.filter(~Q(solvingprogress=None)),
        'schedulers': Scheduler.objects.all(),
        'defvals': {
            'task_description': '{"priority": "LOW"}',
            'sch_json': json.dumps(TEST_JSON),
            'solution_description': '{"resources": {"wall time": 10000}}',
            'nodes_data': json.dumps(TEST_NODES_DATA),
            'tools_data': json.dumps(TEST_TOOLS_DATA),
        },
        'curr_scheduler': request.session.get('scheduler', None),
        'curr_job_id': request.session.get('job id', None)
    })


@login_required
def fill_session(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported'})
    for v in request.POST:
        request.session[v] = request.POST[v]
    return JsonResponse({})


@login_required
@unparallel_group([Job])
def process_job(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported'})
    if 'job id' not in request.POST:
        return JsonResponse({'error': 'Job id is not specified'})
    try:
        job = Job.objects.get(pk=int(request.POST['job id']))
        request.session['job id'] = job.pk
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Job was not found'})
    except ValueError:
        return JsonResponse({'error': 'Unknown error'})

    if job.status != JOB_STATUS[1][0]:
        return JsonResponse({'error': 'Job is not PENDING'})
    change_job_status(job, JOB_STATUS[2][0])
    return JsonResponse({})


@login_required
@unparallel_group([Job])
def launch_job(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported'})
    launcher = service.utils.LaunchTask(request)
    if launcher.new_job:
        return JsonResponse({'new_job_id': launcher.new_job.id})
    elif launcher.parent:
        return JsonResponse({'new_job_id': launcher.parent.id})
    else:
        return JsonResponse({'error': launcher.error})


@login_required
@unparallel_group([SchedulerUser])
def add_scheduler_user(request):
    activate(request.user.extended.language)
    if request.method != 'POST' or 'login' not in request.POST or len(request.POST['login']) == 0 \
            or 'password' not in request.POST or len(request.POST['password']) == 0:
        return JsonResponse({'error': str(UNKNOWN_ERROR)})
    SchedulerUser.objects.get_or_create(
        user=request.user, defaults={'login': request.POST['login'], 'password': request.POST['password']}
    )
    return JsonResponse({})


@unparallel_group([Job])
def update_progress(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You are not signing in'})
    if request.user.extended.role not in [USER_ROLES[2][0], USER_ROLES[4][0]]:
        return JsonResponse({'error': 'No access'})
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported'})
    if 'job id' not in request.session:
        return JsonResponse({'error': 'The job id was not found in session'})
    if 'progress' not in request.POST:
        return JsonResponse({'error': 'Job progress data is required'})

    try:
        job = Job.objects.get(id=request.session['job id'])
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'The job was not found'})
    if job.status != JOB_STATUS[2][0]:
        return JsonResponse({'error': 'The job is not solving'})

    try:
        service.utils.JobProgressData(job).update(request.POST['progress'])
    except service.utils.ServiceError as e:
        return JsonResponse({'error': str(e)})
    except Exception as e:
        logger.exception(e)
        return JsonResponse({'error': 'Unknown error'})
    return JsonResponse({})
