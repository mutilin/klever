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
import os
import re
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.db import transaction
from django.utils.timezone import pytz
from django.utils.translation import ugettext_lazy as _

from bridge.ZipGenerator import ZipStream, CHUNK_SIZE
from bridge.utils import logger, file_get_or_create, unique_id, BridgeException, OpenFiles
from bridge.vars import FORMAT, JOB_STATUS, REPORT_ARCHIVE, JOB_WEIGHT
from jobs.configuration import GetConfiguration
from jobs.jobForm import LoadFilesTree, JobForm
from jobs.models import Job, RunHistory, JobFile
from jobs.utils import change_job_status, remove_jobs_by_id
from reports.UploadReport import UploadReport
from reports.models import Report, ReportRoot, ReportSafe, ReportUnsafe, ReportUnknown, ReportComponent, \
    Component, Computer, ReportAttr, ComponentResource, CoverageArchive, AttrFile, ErrorTraceSource
from reports.utils import AttrData
from service.models import SolvingProgress, JobProgress, Scheduler
from service.utils import StartJobDecision
from tools.utils import Recalculation

ARCHIVE_FORMAT = 12


class KleverCoreArchiveGen:
    def __init__(self, job):
        self.arcname = 'VJ__' + job.identifier + '.zip'
        self.job = job
        self.stream = ZipStream()

    def __iter__(self):
        for f in self.__get_job_files():
            for data in self.stream.compress_file(f['src'], f['path']):
                yield data

        for data in self.stream.compress_string('format', str(self.job.format)):
            yield data

        yield self.stream.close_stream()

    def __get_job_files(self):
        job_file_system = {}
        files_to_add = set()
        for f in self.job.versions.get(version=self.job.version).filesystem_set.all():
            job_file_system[f.id] = {
                'parent': f.parent_id,
                'name': f.name,
                'src': os.path.join(settings.MEDIA_ROOT, f.file.file.name) if f.file is not None else None
            }
            if job_file_system[f.id]['src'] is not None:
                files_to_add.add(f.id)
        job_files = []
        for f_id in files_to_add:
            file_path = job_file_system[f_id]['name']
            parent_id = job_file_system[f_id]['parent']
            while parent_id is not None:
                file_path = os.path.join(job_file_system[parent_id]['name'], file_path)
                parent_id = job_file_system[parent_id]['parent']
            job_files.append({
                'path': os.path.join('root', file_path),
                'src': job_file_system[f_id]['src']
            })
        return job_files


class AttrDataArchive:
    def __init__(self, job):
        self._job = job
        self.stream = ZipStream()

    def __iter__(self):
        for afile in AttrFile.objects.filter(root__job=self._job):
            file_name = os.path.join(settings.MEDIA_ROOT, afile.file.name)
            arc_name = os.path.join('{0}{1}'.format(afile.id, os.path.splitext(afile.file.name)[-1]))
            buf = b''
            for data in self.stream.compress_file(file_name, arc_name):
                buf += data
                if len(buf) > CHUNK_SIZE:
                    yield buf
                    buf = b''
            if len(buf) > 0:
                yield buf
        yield self.stream.close_stream()


class JobArchiveGenerator:
    def __init__(self, job):
        self.job = job
        self.arcname = 'Job-%s.zip' % self.job.identifier[:10]
        self.files_to_add = []
        self.stream = ZipStream()

    def __iter__(self):
        for job_v in self.job.versions.all():
            for data in self.stream.compress_string('version-%s.json' % job_v.version, self.__version_data(job_v)):
                yield data
        for data in self.stream.compress_string('job.json', self.__job_data()):
            yield data

        reportsdata = ReportsData(self.job)
        for data in self.stream.compress_string('reports.json', json.dumps(
                reportsdata.reports, ensure_ascii=False, sort_keys=True, indent=4).encode('utf-8')):
            yield data
        for data in self.stream.compress_string('computers.json', json.dumps(
                reportsdata.computers, ensure_ascii=False, sort_keys=True, indent=4).encode('utf-8')):
            yield data
        for data in self.stream.compress_string('coverage_archives.json', json.dumps(
                reportsdata.coverage, ensure_ascii=False, sort_keys=True, indent=4).encode('utf-8')):
            yield data
        for data in self.stream.compress_string('Resources.json', json.dumps(
                reportsdata.resources, ensure_ascii=False, sort_keys=True, indent=4).encode('utf-8')):
            yield data

        self.__add_reports_files()
        self.__add_coverage_files(reportsdata.coverage_arch_names)
        for file_path, arcname in self.files_to_add:
            for data in self.stream.compress_file(file_path, arcname):
                yield data
        if AttrFile.objects.filter(root__job=self.job).count() > 0:
            for data in self.stream.compress_stream('AttrData.zip', AttrDataArchive(self.job)):
                yield data
        yield self.stream.close_stream()

    def __version_data(self, job_v):
        hash_sums = set(h for h, in job_v.filesystem_set.exclude(file=None).values_list('file__hash_sum'))
        for f in JobFile.objects.filter(hash_sum__in=hash_sums):
            self.files_to_add.append((f.file.path, os.path.join('JobFiles', f.file.name)))

        return json.dumps({
            'files': json.dumps([LoadFilesTree(self.job.id, job_v.version).as_json()], ensure_ascii=False),
            'comment': job_v.comment, 'global_role': job_v.global_role, 'description': job_v.description
        }, ensure_ascii=False, sort_keys=True, indent=4).encode('utf-8')

    def __job_data(self):
        return json.dumps({
            'archive_format': ARCHIVE_FORMAT, 'format': self.job.format, 'identifier': self.job.identifier,
            'status': self.job.status, 'name': self.job.name, 'weight': self.job.weight,
            'run_history': self.__add_run_history_files(), 'progress': self.__get_progress_data()
        }, ensure_ascii=False, sort_keys=True, indent=4).encode('utf-8')

    def __get_progress_data(self):
        data = {}
        try:
            sp = SolvingProgress.objects.get(job=self.job)
        except ObjectDoesNotExist:
            pass
        else:
            data.update({
                'priority': sp.priority, 'scheduler': sp.scheduler.type,
                'start_date': sp.start_date.timestamp() if sp.start_date is not None else None,
                'finish_date': sp.finish_date.timestamp() if sp.finish_date is not None else None,
                'tasks_total': sp.tasks_total, 'tasks_pending': sp.tasks_pending,
                'tasks_processing': sp.tasks_processing, 'tasks_finished': sp.tasks_finished,
                'tasks_error': sp.tasks_error, 'tasks_cancelled': sp.tasks_cancelled,
                'solutions': sp.solutions, 'error': sp.error
            })
        try:
            jp = JobProgress.objects.get(job=self.job)
        except ObjectDoesNotExist:
            pass
        else:
            data.update({
                'total_sj': jp.total_sj, 'failed_sj': jp.failed_sj, 'solved_sj': jp.solved_sj,
                'start_sj': jp.start_sj.timestamp() if jp.start_sj is not None else None,
                'finish_sj': jp.finish_sj.timestamp() if jp.finish_sj is not None else None,
                'total_ts': jp.total_ts, 'failed_ts': jp.failed_ts, 'solved_ts': jp.solved_ts,
                'start_ts': jp.start_ts.timestamp() if jp.start_ts is not None else None,
                'finish_ts': jp.finish_ts.timestamp() if jp.finish_ts is not None else None,
                'expected_time_sj': jp.expected_time_sj, 'expected_time_ts': jp.expected_time_ts,
                'gag_text_sj': jp.gag_text_sj, 'gag_text_ts': jp.gag_text_ts
            })
        return data

    def __add_run_history_files(self):
        data = []
        for rh in self.job.runhistory_set.order_by('date'):
            self.files_to_add.append((
                os.path.join(settings.MEDIA_ROOT, rh.configuration.file.name),
                os.path.join('Configurations', "%s.json" % rh.pk)
            ))
            data.append({'id': rh.pk, 'status': rh.status, 'date': rh.date.timestamp()})
        return data

    def __add_reports_files(self):
        try:
            root_id = ReportRoot.objects.get(job=self.job).id
        except ObjectDoesNotExist:
            return
        for report in ReportSafe.objects.filter(root_id=root_id):
            if report.proof:
                self.files_to_add.append((
                    os.path.join(settings.MEDIA_ROOT, report.proof.name),
                    os.path.join('ReportSafe', 'proof_%s.zip' % report.pk)
                ))
        for report in ReportUnsafe.objects.filter(root_id=root_id):
            self.files_to_add.append((
                os.path.join(settings.MEDIA_ROOT, report.error_trace.name),
                os.path.join('ReportUnsafe', 'trace_%s.zip' % report.pk)
            ))
        for report in ReportUnknown.objects.filter(root_id=root_id):
            self.files_to_add.append((
                os.path.join(settings.MEDIA_ROOT, report.problem_description.name),
                os.path.join('ReportUnknown', 'problem_%s.zip' % report.pk)
            ))
        for report in ReportComponent.objects.filter(root_id=root_id):
            if report.log:
                self.files_to_add.append((
                    os.path.join(settings.MEDIA_ROOT, report.log.name),
                    os.path.join('ReportComponent', 'log_%s.zip' % report.pk)
                ))
            if report.verifier_input:
                self.files_to_add.append((
                    os.path.join(settings.MEDIA_ROOT, report.verifier_input.name),
                    os.path.join('ReportComponent', 'verifier_input_%s.zip' % report.pk)
                ))
        for source in ErrorTraceSource.objects.filter(root_id=root_id):
            self.files_to_add.append((
                os.path.join(settings.MEDIA_ROOT, source.archive.name),
                os.path.join('ErrorTraceSource', 'source_%s.zip' % source.id)
            ))

    def __add_coverage_files(self, archives):
        for i in range(len(archives)):
            self.files_to_add.append((
                os.path.join(settings.MEDIA_ROOT, archives[i]), os.path.join('Coverages', '%s.zip' % i)
            ))


class JobsArchivesGen:
    def __init__(self, jobs):
        self.jobs = jobs
        self.stream = ZipStream()

    def __iter__(self):
        for job in self.jobs:
            jobgen = JobArchiveGenerator(job)
            buf = b''
            for data in self.stream.compress_stream(jobgen.arcname, jobgen):
                buf += data
                if len(buf) > CHUNK_SIZE:
                    yield buf
                    buf = b''
            if len(buf) > 0:
                yield buf
        yield self.stream.close_stream()


class JobsTreesGen:
    def __init__(self, jobs_ids):
        self._tree = {}
        self.jobs = self.__get_jobs(jobs_ids)
        self.stream = ZipStream()

    def __iter__(self):
        for job in self.jobs:
            jobgen = JobArchiveGenerator(job)
            buf = b''
            for data in self.stream.compress_stream(jobgen.arcname, jobgen):
                buf += data
                if len(buf) > CHUNK_SIZE:
                    yield buf
                    buf = b''
            if len(buf) > 0:
                yield buf
        for data in self.stream.compress_string('tree.json', json.dumps(self._tree, sort_keys=True, indent=2)):
            yield data
        yield self.stream.close_stream()

    def __get_jobs(self, jobs_ids):
        jobs = []
        for j in Job.objects.filter(id__in=jobs_ids):
            jobs.append(j)
            self._tree[j.identifier] = None
        parent_ids = jobs_ids
        while len(parent_ids) > 0:
            new_parents = []
            for j in Job.objects.filter(parent_id__in=parent_ids).select_related('parent'):
                if j.identifier not in self._tree:
                    jobs.append(j)
                    new_parents.append(j.id)
                self._tree[j.identifier] = j.parent.identifier
            parent_ids = new_parents
        return jobs


class ReportsData:
    def __init__(self, job):
        self.computers = {}
        self.coverage = []
        self.coverage_arch_names = []
        self._parents = {None: None}
        try:
            self.root = ReportRoot.objects.get(job=job)
        except ObjectDoesNotExist:
            self.reports = []
            self.resources = []
        else:
            self.reports = self.__reports_data()
            self.__get_coverage_data()
            self.resources = self.__get_resources_data()

    def __report_component_data(self, report):
        data = None
        if report.data:
            with report.data as fp:
                data = fp.read().decode('utf8')
        if report.computer_id not in self.computers:
            self.computers[str(report.computer_id)] = report.computer.description
        self._parents[report.id] = report.identifier
        return {
            'pk': report.pk,
            'parent': self._parents[report.parent_id],
            'identifier': report.identifier,
            'computer': str(report.computer_id),
            'component': report.component.name,
            'verification': report.verification,
            'resource': {
                'cpu_time': report.cpu_time,
                'wall_time': report.wall_time,
                'memory': report.memory,
            } if all(x is not None for x in [report.cpu_time, report.wall_time, report.memory]) else None,
            'start_date': report.start_date.timestamp(),
            'finish_date': report.finish_date.timestamp() if report.finish_date is not None else None,
            'data': data,
            'covnum': report.covnum,
            'attrs': []
        }

    def __report_leaf_data(self, report):
        data = {
            'pk': report.pk,
            'parent': self._parents[report.parent_id],
            'identifier': report.identifier,
            'cpu_time': report.cpu_time,
            'wall_time': report.wall_time,
            'memory': report.memory,
            'attrs': []
        }
        if isinstance(report, ReportUnknown):
            data['component'] = report.component.name
        elif isinstance(report, ReportUnsafe):
            data['trace_id'] = report.trace_id
            data['source'] = report.source_id
        elif isinstance(report, ReportSafe) and report.source_id:
            data['source'] = report.source_id
        return data

    def __reports_data(self):
        reports = []
        report_index = {}
        i = 0
        for rc in ReportComponent.objects.filter(root=self.root).select_related('component').order_by('id'):
            report_index[rc.pk] = i
            reports.append(self.__report_component_data(rc))
            i += 1
        reports.append(ReportSafe.__name__)
        i += 1
        for safe in ReportSafe.objects.filter(root=self.root):
            report_index[safe.pk] = i
            reports.append(self.__report_leaf_data(safe))
            i += 1
        reports.append(ReportUnsafe.__name__)
        i += 1
        for unsafe in ReportUnsafe.objects.filter(root=self.root):
            report_index[unsafe.pk] = i
            reports.append(self.__report_leaf_data(unsafe))
            i += 1
        reports.append(ReportUnknown.__name__)
        i += 1
        for unknown in ReportUnknown.objects.filter(root=self.root).select_related('component'):
            report_index[unknown.pk] = i
            reports.append(self.__report_leaf_data(unknown))
            i += 1
        for ra in ReportAttr.objects.filter(report__root=self.root).select_related('attr', 'attr__name', 'data')\
                .order_by('id'):
            ra_data = None
            if ra.data is not None:
                ra_data = os.path.join('{0}{1}'.format(ra.data_id, os.path.splitext(ra.data.file.name)[-1]))
            reports[report_index[ra.report_id]]['attrs'].append([
                ra.attr.name.name, ra.attr.value, ra.compare, ra.associate, ra_data
            ])
        return reports

    def __get_coverage_data(self):
        for carch in CoverageArchive.objects.filter(report__root=self.root):
            self.coverage.append([carch.report_id, carch.identifier])
            self.coverage_arch_names.append(carch.archive.name)

    def __get_resources_data(self):
        res_data = []
        for r in ComponentResource.objects.filter(report__root=self.root):
            res_data.append({
                'id': r.report_id, 'component': r.component.name if r.component is not None else None,
                'wall_time': r.wall_time, 'cpu_time': r.cpu_time, 'memory': r.memory
            })
        return res_data


class UploadTree:
    def __init__(self, parent_id, user, jobs_dir):
        self._parent_id = parent_id
        self._user = user
        self._jobsdir = jobs_dir

        self._uploaded = set()
        self._tree = self.__get_tree()

        try:
            self.__upload_tree()
        except Exception:
            remove_jobs_by_id(self._user, list(j.id for j in Job.objects.filter(identifier__in=self._uploaded)))
            raise

    def __get_tree(self):
        tree_fname = os.path.join(self._jobsdir, 'tree.json')
        if not os.path.exists(tree_fname):
            raise BridgeException(_('The file with tree structure was not found'))
        with open(tree_fname, mode='r', encoding='utf8') as fp:
            return json.loads(fp.read())

    def __get_jobs_order(self):
        jobs = []
        for j_id in self._tree:
            if self._tree[j_id] is None:
                jobs.append(j_id)
        while True:
            has_child = False
            for j_id in self._tree:
                if self._tree[j_id] in jobs and j_id not in jobs:
                    jobs.append(j_id)
                    has_child = True
            if not has_child:
                break
        return jobs

    def __upload_tree(self):
        for j_id in self.__get_jobs_order():
            jobzip_name = os.path.join(self._jobsdir, 'Job-%s.zip' % j_id[:10])
            if not os.path.exists(jobzip_name):
                raise BridgeException(_('One of the job archives was not found'))
            if self._tree[j_id] is None:
                parent_id = self._parent_id
            elif self._tree[j_id] in self._uploaded:
                parent_id = self._tree[j_id]
            else:
                logger.error('The parent was not uploaded before the child')
                raise BridgeException()
            self.__upload_job(jobzip_name, parent_id)

    def __upload_job(self, jobarch, parent_id):
        try:
            jobdir = self.__extract_archive(jobarch)
        except Exception as e:
            logger.exception("Archive extraction failed: %s" % e, stack_info=True)
            raise BridgeException(_('Extraction of the archive "%(arcname)s" has failed') % {
                'arcname': os.path.basename(jobarch)
            })
        try:
            res = UploadJob(parent_id, self._user, jobdir.name)
        except BridgeException as e:
            raise BridgeException(_('Creating the job from archive "%(arcname)s" failed: %(message)s') % {
                    'arcname': os.path.basename(jobarch), 'message': str(e)
                })
        except Exception as e:
            logger.exception(e)
            raise BridgeException(_('Creating the job from archive "%(arcname)s" failed: %(message)s') % {
                    'arcname': os.path.basename(jobarch), 'message': _('The job archive is corrupted')
                })
        self._uploaded.add(res.job.identifier)

    def __extract_archive(self, jobarch):
        self.__is_not_used()
        with open(jobarch, mode='rb') as fp:
            if os.path.splitext(jobarch)[-1] != '.zip':
                raise ValueError('Only zip archives are supported')
            with zipfile.ZipFile(fp, mode='r') as zfp:
                tmp_dir_name = tempfile.TemporaryDirectory()
                zfp.extractall(tmp_dir_name.name)
            return tmp_dir_name

    def __is_not_used(self):
        pass


class UploadJob:
    def __init__(self, parent_id, user, job_dir):
        self._parent_id = '' if parent_id == 'null' else parent_id
        self.job = None
        self._user = user
        self._jobdir = job_dir
        self._jobdata = self.__read_json_file('job.json')
        self.__check_job_data()
        self.__upload_job_files()
        self.__upload_job()
        self.__upload_reports()

    def __read_json_file(self, rel_path):
        full_path = os.path.join(self._jobdir, rel_path)
        if os.path.exists(full_path):
            with open(full_path, encoding='utf8') as fp:
                return json.load(fp)
        return None

    def __upload_job_files(self):
        # If 'JobFiles' doesn't exist then the job doiesn't have files or archive is corrupted.
        # It'll be checked while files tree is uploading.
        for dir_path, dir_names, file_names in os.walk(os.path.join(self._jobdir, 'JobFiles')):
            for file_name in file_names:
                try:
                    file_get_or_create(open(os.path.join(dir_path, file_name), mode='rb'), file_name, JobFile, True)
                except Exception as e:
                    logger.exception("Can't save job files to DB: %s" % e)
                    raise BridgeException(_("Creating job's file failed"))

    def __check_job_data(self):
        if not isinstance(self._jobdata, dict):
            raise ValueError('job.json file was not found or contains wrong data')
        if self._jobdata.get('archive_format') != ARCHIVE_FORMAT:
            raise BridgeException(_("The job archive format is not supported"))
        if any(x not in self._jobdata for x in ['name', 'status', 'run_history', 'weight', 'progress']):
            logger.error("The job data is not full")
            raise BridgeException(_("The job archive was corrupted"))
        if self._jobdata.get('format') != FORMAT:
            logger.error('Unsupported job format: %s' % self._jobdata['format'])
            raise BridgeException(_("The job format is not supported"))
        if self._jobdata['status'] not in list(x[0] for x in JOB_STATUS):
            raise ValueError("The job status is wrong: %s" % self._jobdata['status'])
        if self._jobdata['weight'] not in set(w[0] for w in JOB_WEIGHT):
            raise ValueError('Wrong job weight: %s' % self._jobdata['weight'])

        if 'identifier' in self._jobdata and (not isinstance(self._jobdata['identifier'], str)
                                              or len(self._jobdata['identifier']) == 0):
            del self._jobdata['identifier']

    def __get_job_versions(self):
        versions_data = {}
        for fname in os.listdir(self._jobdir):
            full_path = os.path.join(self._jobdir, fname)
            if not os.path.isfile(full_path) or not fname.startswith('version-'):
                continue
            m = re.match('version-(\d+)\.json', fname)
            if m is None:
                continue
            version = int(m.group(1))
            with open(full_path, encoding='utf8') as fp:
                versions_data[version] = json.load(fp)
            if any(x not in versions_data[version] for x in ['description', 'comment', 'global_role', 'files']):
                logger.error("The job version data is not full")
                raise BridgeException(_("The job archive was corrupted"))

        if len(versions_data) == 0:
            raise ValueError("There are no job's versions in the archive")
        return list(versions_data[v] for v in sorted(versions_data))

    def __upload_job(self):
        versions = self.__get_job_versions()

        # Upload 1st version of job (creating new job)
        if Job.objects.filter(identifier=self._jobdata.get('identifier')).count() > 0:
            del self._jobdata['identifier']
        job_name = self._jobdata['name']
        jobs_counter = Job.objects.filter(name__startswith=job_name).count()
        if jobs_counter > 0:
            job_name = "{} ({})".format(job_name, jobs_counter)
            self._jobdata['name'] = job_name

        self.job = JobForm(self._user, None, 'copy').save({
            'identifier': self._jobdata.get('identifier'), 'parent': self._parent_id,
            'name': self._jobdata['name'], 'comment': versions[0]['comment'], 'description': versions[0]['description'],
            'global_role': versions[0]['global_role'], 'file_data': versions[0]['files'],
            'weight': self._jobdata['weight']
        })

        last_conf = None
        # Uploading job's run history
        try:
            for rh in self._jobdata['run_history']:
                if rh['status'] not in list(x[0] for x in JOB_STATUS):
                    logger.error('Wrong status: %s' % rh['status'])
                    raise BridgeException(_("The job archive is corrupted"))
                run_conf = os.path.join(self._jobdir, 'Configurations', '{0}.json'.format(rh['id']))
                if not os.path.exists(run_conf):
                    logger.error('Job decision configuration was not found')
                    raise BridgeException(_("The job archive was corrupted"))
                with open(run_conf, mode='rb') as fp:
                    conf_file = file_get_or_create(fp, 'config.json', JobFile)[0]
                RunHistory.objects.create(
                    job=self.job, status=rh['status'], configuration=conf_file,
                    date=datetime.fromtimestamp(rh['date'], pytz.timezone('UTC'))
                )
                last_conf = conf_file
        except Exception as e:
            self.job.delete()
            raise ValueError("Run history data is corrupted: %s" % e)

        # Uploading job's versions
        for version_data in versions[1:]:
            try:
                self.job = JobForm(self._user, self.job, 'edit').save({
                    'last_version': self.job.version, 'parent': self._parent_id, 'name': self._jobdata['name'],
                    'comment': version_data['comment'], 'description': version_data['description'],
                    'global_role': version_data['global_role'], 'file_data': version_data['files']
                })
            except Exception as e:
                logger.exception(e)
                self.job.delete()
                raise BridgeException(_('Uploading job version has failed'))

        # Change job's status as it was in downloaded archive
        change_job_status(self.job, self._jobdata['status'])
        self.__create_progress(self.job, self._jobdata['progress'], last_conf)

    def __get_reports_files(self):
        report_files = {}
        for name in ['ReportSafe', 'ReportUnsafe', 'ReportUnknown', 'ReportComponent', 'ErrorTraceSource']:
            dir_path = os.path.join(self._jobdir, name)
            if not os.path.isdir(dir_path):
                continue
            for arcname in os.listdir(dir_path):
                m = re.match('(.*)_(\d+)\.zip', arcname)
                if m is not None:
                    report_files[(name, m.group(1), int(m.group(2)))] = os.path.join(dir_path, arcname)
        return report_files

    def __get_coverage_files(self):
        coverage_files = {}
        coverage_path = os.path.join(self._jobdir, 'Coverages')
        if os.path.isdir(coverage_path):
            for arcname in os.listdir(coverage_path):
                m = re.match('(\d+)\.zip', arcname)
                if m is not None:
                    coverage_files[int(m.group(1))] = os.path.join(coverage_path, arcname)
        return coverage_files

    def __attr_data(self):
        attr_data = None
        attr_data_file = os.path.join(self._jobdir, 'AttrData.zip')
        if os.path.isfile(attr_data_file):
            attr_data = File(open(attr_data_file, mode='rb'))
        return attr_data

    def __upload_reports(self):
        ReportRoot.objects.create(user=self._user, job=self.job)
        try:
            UploadReports(
                self.job, self.__read_json_file('reports.json'), self.__get_reports_files(),
                self.__read_json_file('computers.json'), self.__read_json_file('Resources.json'),
                self.__read_json_file('coverage_archives.json'), self.__get_coverage_files(), self.__attr_data()
            )
        except BridgeException:
            self.job.delete()
            raise
        except Exception as e:
            logger.exception("Uploading reports failed: %s" % e, stack_info=True)
            self.job.delete()
            raise BridgeException(_("Unknown error while uploading reports"))

    def __create_progress(self, job, data, conf_file):
        if 'scheduler' in data:
            if conf_file is None:
                raise ValueError("The job archive doesn't have run history files")
            try:
                scheduler = Scheduler.objects.get(type=data['scheduler'])
            except ObjectDoesNotExist:
                raise BridgeException(_('Scheduler for the job was not found'))
            SolvingProgress.objects.create(
                job=job, scheduler=scheduler, fake=True, priority=data['priority'],
                start_date=datetime.fromtimestamp(data['start_date'], pytz.timezone('UTC'))
                if data['start_date'] is not None else None,
                finish_date=datetime.fromtimestamp(data['finish_date'], pytz.timezone('UTC'))
                if data['finish_date'] is not None else None,
                tasks_total=data['tasks_total'], tasks_pending=data['tasks_pending'],
                tasks_processing=data['tasks_processing'], tasks_finished=data['tasks_finished'],
                tasks_error=data['tasks_error'], tasks_cancelled=data['tasks_cancelled'],
                solutions=data['solutions'], error=data['error'], configuration=conf_file
            )
        if 'total_sj' in data:
            JobProgress.objects.create(
                job=job,
                total_sj=data['total_sj'], failed_sj=data['failed_sj'], solved_sj=data['solved_sj'],
                start_sj=datetime.fromtimestamp(data['start_sj'], pytz.timezone('UTC'))
                if data['start_sj'] is not None else None,
                finish_sj=datetime.fromtimestamp(data['finish_sj'], pytz.timezone('UTC'))
                if data['finish_sj'] is not None else None,
                total_ts=data['total_ts'], failed_ts=data['failed_ts'], solved_ts=data['solved_ts'],
                start_ts=datetime.fromtimestamp(data['start_ts'], pytz.timezone('UTC'))
                if data['start_ts'] is not None else None,
                finish_ts=datetime.fromtimestamp(data['finish_ts'], pytz.timezone('UTC'))
                if data['finish_ts'] is not None else None,
                expected_time_sj=data['expected_time_sj'], expected_time_ts=data['expected_time_ts'],
                gag_text_sj=data['gag_text_sj'], gag_text_ts=data['gag_text_ts']
            )


class UploadReports:
    def __init__(self, job, data, files, computers, resources, coverage, cov_archives, attr_data):
        self.data = data
        self._job = job
        self._files = files
        self._computers = self.__upload_computers(computers)
        self._parents = {None: None}
        self._indexes = {}
        self._tree = []
        self._safes = []
        self._unsafes = []
        self._unknowns = []
        self._components = {}
        self._rc_id_map = {}

        if isinstance(self.data, list):
            self.__upload_reports()
            self.__upload_attrs(attr_data)
            # TODO: fix this
            # self.__upload_coverage(coverage, cov_archives)
            self.__upload_resources_cache(resources)
            Recalculation('for_uploaded', json.dumps([self._job.pk], ensure_ascii=False))

    def __fix_identifer(self, i):
        m = re.match('.*?(/.*)', self.data[i]['identifier'])
        if m is None:
            self.data[i]['identifier'] = self._job.identifier
        else:
            self.data[i]['identifier'] = self._job.identifier + m.group(1)
        if self.data[i]['parent'] is not None:
            m = re.match('.*?(/.*)', self.data[i]['parent'])
            if m is None:
                self.data[i]['parent'] = self._job.identifier
            else:
                self.data[i]['parent'] = self._job.identifier + m.group(1)

    def __upload_computers(self, computers):
        db_computers = {}
        if isinstance(computers, dict):
            for c_id in computers:
                computer = Computer.objects.get_or_create(description=computers[c_id])[0]
                db_computers[c_id] = computer.id
        return db_computers

    def __upload_attrs(self, attr_data):
        attrs = AttrData(self._job.reportroot.id, attr_data)
        for report in Report.objects.filter(root=self._job.reportroot).only('id', 'identifier'):
            i = self._indexes[report.identifier]
            for attr in self.data[i]['attrs']:
                attrs.add(report.id, *attr)
        attrs.upload()

    def __upload_reports(self):
        curr_func = self.__add_report_component
        for i in range(len(self.data)):
            if isinstance(self.data[i], dict):
                self.__fix_identifer(i)
                curr_func(i)
            elif isinstance(self.data[i], str) and self.data[i] == ReportSafe.__name__:
                def curr_func(x):
                    self._safes.append(x)
                    self._indexes[self.data[x]['identifier']] = x
            elif isinstance(self.data[i], str) and self.data[i] == ReportUnsafe.__name__:
                def curr_func(x):
                    self._unsafes.append(x)
                    self._indexes[self.data[x]['identifier']] = x
            elif isinstance(self.data[i], str) and self.data[i] == ReportUnknown.__name__:
                def curr_func(x):
                    self._unknowns.append(x)
                    self._indexes[self.data[x]['identifier']] = x
        for lvl in range(len(self._tree)):
            self.__upload_report_components(lvl)
            for report in ReportComponent.objects.filter(root=self._job.reportroot):
                self._parents[report.identifier] = report.id
        self.__upload_safe_reports()
        self.__upload_unsafe_reports()
        self.__upload_unknown_reports()

    @transaction.atomic
    def __upload_report_components(self, lvl):
        for identifier in self._tree[lvl]:
            i = self._indexes[identifier]
            report = ReportComponent(
                identifier=identifier, root=self._job.reportroot, covnum=self.data[i]['covnum'],
                parent_id=self._parents[self.data[i].get('parent')],
                computer_id=self._computers[self.data[i]['computer']],
                component_id=self.__get_component(self.data[i]['component']),
                verification=self.data[i]['verification'],
                start_date=datetime.fromtimestamp(self.data[i]['start_date'], pytz.timezone('UTC')),
                finish_date=datetime.fromtimestamp(self.data[i]['finish_date'], pytz.timezone('UTC'))
                if self.data[i]['finish_date'] is not None else None
            )
            if self.data[i]['resource'] is not None:
                report.cpu_time = self.data[i]['resource']['cpu_time']
                report.wall_time = self.data[i]['resource']['wall_time']
                report.memory = self.data[i]['resource']['memory']

            log_id = (ReportComponent.__name__, 'log', self.data[i]['pk'])
            if log_id in self._files:
                with open(self._files[log_id], mode='rb') as fp:
                    report.add_log(REPORT_ARCHIVE['log'], fp)

            verifier_input_id = (ReportComponent.__name__, 'verifier_input', self.data[i]['pk'])
            if verifier_input_id in self._files:
                with open(self._files[verifier_input_id], mode='rb') as fp:
                    report.add_verifier_input(REPORT_ARCHIVE['verifier input'], fp)

            if self.data[i]['data'] is not None:
                report.new_data('report-data.json', BytesIO(self.data[i]['data'].encode('utf8')))

            report.save()
            self._rc_id_map[self.data[i]['pk']] = report.id

    @transaction.atomic
    def __upload_safe_reports(self):
        sources = {}
        for i in self._safes:
            if self.data[i]['source'] not in sources:
                source_arch_id = (ErrorTraceSource.__name__, 'source', self.data[i]['source'])
                new_source = ErrorTraceSource(root=self._job.reportroot)
                with open(self._files[source_arch_id], mode='rb') as fp:
                    new_source.add_sources(REPORT_ARCHIVE['sources'], fp, True)
                sources[self.data[i]['source']] = new_source.id
            report = ReportSafe(
                root=self._job.reportroot, identifier=self.data[i]['identifier'],
                parent_id=self._parents[self.data[i]['parent']], source_id=sources[self.data[i]['source']],
                cpu_time=self.data[i]['cpu_time'], wall_time=self.data[i]['wall_time'], memory=self.data[i]['memory']
            )
            proof_id = (ReportSafe.__name__, 'proof', self.data[i]['pk'])
            if proof_id in self._files:
                with open(self._files[proof_id], mode='rb') as fp:
                    report.add_proof(REPORT_ARCHIVE['proof'], fp)
            report.save()

    @transaction.atomic
    def __upload_unsafe_reports(self):
        sources = {}
        for i in self._unsafes:
            # Upload error trace sources if it was not uploaded for already created error traces
            if self.data[i]['source'] not in sources:
                source_arch_id = (ErrorTraceSource.__name__, 'source', self.data[i]['source'])
                new_source = ErrorTraceSource(root=self._job.reportroot)
                with open(self._files[source_arch_id], mode='rb') as fp:
                    new_source.add_sources(REPORT_ARCHIVE['sources'], fp, True)
                sources[self.data[i]['source']] = new_source.id

            # Check if error trace identifier exists and is unique
            if 'trace_id' not in self.data[i] or \
                    ReportUnsafe.objects.filter(trace_id=self.data[i]['trace_id']).count() > 0:
                self.data[i]['trace_id'] = unique_id()

            report = ReportUnsafe(
                root=self._job.reportroot, identifier=self.data[i]['identifier'], trace_id=self.data[i]['trace_id'],
                source_id=sources[self.data[i]['source']], parent_id=self._parents[self.data[i]['parent']],
                cpu_time=self.data[i]['cpu_time'], wall_time=self.data[i]['wall_time'], memory=self.data[i]['memory']
            )
            trace_id = (ReportUnsafe.__name__, 'trace', self.data[i]['pk'])
            with open(self._files[trace_id], mode='rb') as fp:
                report.add_trace(REPORT_ARCHIVE['error trace'], fp, True)

    @transaction.atomic
    def __upload_unknown_reports(self):
        for i in self._unknowns:
            report = ReportUnknown(
                root=self._job.reportroot, identifier=self.data[i]['identifier'],
                parent_id=self._parents[self.data[i]['parent']],
                component_id=self.__get_component(self.data[i]['component']),
                cpu_time=self.data[i]['cpu_time'], wall_time=self.data[i]['wall_time'], memory=self.data[i]['memory']
            )
            problem_id = (ReportUnknown.__name__, 'problem', self.data[i]['pk'])
            with open(self._files[problem_id], mode='rb') as fp:
                report.add_problem_desc(REPORT_ARCHIVE['problem desc'], fp)
            report.save()

    def __get_component(self, name):
        if name not in self._components:
            component = Component.objects.get_or_create(name=name)[0]
            self._components[name] = component.id
        return self._components[name]

    def __add_report_component(self, i):
        p_id = self.data[i].get('parent')
        if p_id is None:
            self.__add_to_tree(0, i)
        else:
            for j in range(len(self._tree)):
                if p_id in self._tree[j]:
                    self.__add_to_tree(j + 1, i)
                    break
            else:
                raise ValueError('The report parent was not found in data')

    def __add_to_tree(self, lvl, i):
        while len(self._tree) <= lvl:
            self._tree.append(set())
        self._tree[lvl].add(self.data[i]['identifier'])
        self._indexes[self.data[i]['identifier']] = i

    @transaction.atomic
    def __upload_coverage(self, coverage, archives):
        if not isinstance(coverage, list):
            return
        for i in range(len(coverage)):
            if i not in archives:
                raise FileNotFoundError('Coverage archive was not found')
            if coverage[i][0] not in self._rc_id_map:
                raise ValueError('Component report was not uploaded')
            carch = CoverageArchive(report_id=self._rc_id_map[coverage[i][0]], identifier=coverage[i][1])
            with open(archives[i], mode='rb') as fp:
                carch.save_archive(REPORT_ARCHIVE['coverage'], fp)

    def __upload_resources_cache(self, resources):
        if not isinstance(resources, list):
            raise ValueError('Resources must be a list')
        components = {}
        res_cache = []
        for res_data in resources:
            old_id = res_data['id']
            if old_id not in self._rc_id_map:
                continue
            component = res_data['component']
            if component is not None:
                if component not in components:
                    components[component] = Component.objects.get_or_create(name=component)[0].id
                component = components[component]
            res_cache.append(ComponentResource(
                report_id=self._rc_id_map[old_id], component_id=component,
                cpu_time=res_data['cpu_time'], wall_time=res_data['wall_time'], memory=res_data['memory']
            ))
        ComponentResource.objects.bulk_create(res_cache)


class UploadReportsWithoutDecision:
    reports_file = 'reports.json'
    fields = {
        'start': ['id', 'parent id', 'name', 'attrs', 'attr data', 'comp', 'config'],
        'finish': ['id', 'data', 'resources', 'log', 'coverage'],
        'verification': [
            'id', 'parent id', 'name', 'attrs', 'attr data', 'comp', 'resources',
            'log', 'coverage', 'input files of static verifiers', 'config'
        ],
        'job coverage': [
            'id', 'parent id', 'name', 'attrs', 'attr data', 'resources', 'coverage'
        ],
        'verification finish': ['id'],
        'safe': ['id', 'parent id', 'attrs', 'attr data', 'proof', 'sources'],
        'unsafe': ['id', 'parent id', 'attrs', 'attr data', 'sources', 'error traces'],
        'unknown': ['id', 'parent id', 'attrs', 'attr data', 'problem desc']
    }
    files_fields = [
        'attr data', 'log', 'coverage', 'input files of static verifiers',
        'proof', 'sources', 'error traces', 'problem desc', 'coverage sources'
    ]

    def __init__(self, job, user, reports_dir):
        self._job = job
        self._user = user
        self._reports_dir = reports_dir
        self._data = self.__read_reports_data()
        self.source_archives = dict()
        self.__prepare_job()
        try:
            self.__upload_children(None)
        except Exception:
            ReportRoot.objects.get(job=self._job).delete()
            self._job.status = JOB_STATUS[4][0]
            self._job.save()
            raise
        change_job_status(self._job, JOB_STATUS[3][0])

    def __read_reports_data(self):
        reports_file = os.path.join(self._reports_dir, self.reports_file)
        if not os.path.isfile(reports_file):
            raise BridgeException(_("The archive doesn't contain main reports file"))
        with open(reports_file, encoding='utf8') as fp:
            data = json.load(fp)
        if not isinstance(data, list) or len(data) == 0:
            raise BridgeException(_('Wrong format of main reports file'))
        return data

    def __prepare_job(self):
        StartJobDecision(self._user, self._job.id, GetConfiguration().configuration, fake=True)
        change_job_status(self._job, JOB_STATUS[2][0])
        self._job = Job.objects.get(id=self._job.id)

    def __upload_children(self, parent_id):
        actions = {
            'component': self.__upload_component, 'verification': self.__upload_verification,
            'safe': self.__upload_leaf, 'unsafe': self.__upload_leaf, 'unknown': self.__upload_leaf,
            'job coverage': self.__upload_leaf
        }
        for report in self._data:
            if report['parent id'] == parent_id:
                actions[report['type']](report)

    def __upload_component(self, data):
        self.__upload(data, 'start')
        self.__upload_children(data['id'])
        self.__upload(data, 'finish')

    def __upload_verification(self, data):
        self.__upload(data, 'verification')
        self.__upload_children(data['id'])
        self.__upload(data, 'verification finish')

    def __upload_leaf(self, data):
        self.__upload(data, data['type'])

    def __upload(self, data, report_type):
        # Collecting report data
        report = data.copy()
        if 'resources' in self.fields[report_type] and 'resources' not in report:
            report['resources'] = {'CPU time': 0, 'wall time': 0, 'memory size': 0}
        if report_type == 'start' and report['id'] == '/':
            del report['parent id']
        report['type'] = report_type

        # Collecting report files
        files = []
        for f in self.files_fields:
            if f in report:
                if isinstance(report[f], str):
                    files.append(os.path.join(self._reports_dir, report[f]))
                elif isinstance(report[f], list):
                    files.extend(list(os.path.join(self._reports_dir, p) for p in report[f]))
                elif isinstance(report[f], dict):
                    files.extend(list(os.path.join(self._reports_dir, p) for p in report[f].values()))

        # Uploading report
        try:
            with OpenFiles(*files, rel_path=self._reports_dir) as archives:
                res = UploadReport(self._job, report, archives=archives, source_archives=self.source_archives)
            if res.error is not None:
                raise ValueError(res.error)
        except FileNotFoundError:
            logger.error('Files {} were not found'.format(files))
