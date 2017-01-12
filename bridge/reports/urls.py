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

from django.conf.urls import url
from reports import views


urlpatterns = [
    url(r'^component/(?P<job_id>[0-9]+)/(?P<report_id>[0-9]+)/$', views.report_component, name='component'),
    url('^log/(?P<report_id>[0-9]+)/$', views.get_component_log, name='log'),
    url('^logcontent/(?P<report_id>[0-9]+)/$', views.get_log_content),
    url(r'^component/(?P<report_id>[0-9]+)/(?P<ltype>unsafes|safes|unknowns)/$', views.report_list, name='list'),
    url(r'^component/(?P<report_id>[0-9]+)/(?P<ltype>unsafes|safes)/tag/(?P<tag_id>[0-9]+)$',
        views.report_list_tag, name='list_tag'),
    url(r'^component/(?P<report_id>[0-9]+)/(?P<ltype>unsafes|safes)/(?P<verdict>[0-9])/$',
        views.report_list_by_verdict, name='list_verdict'),
    url(r'^component/(?P<report_id>[0-9]+)/(?P<ltype>unsafes|safes|unknowns)/mark/(?P<mark_id>[0-9]+)/$',
        views.report_list_by_mark, name='list_mark'),
    url(r'^component/(?P<report_id>[0-9]+)/(?P<ltype>unsafes|safes|unknowns)/attr/(?P<attr_id>[0-9]+)/$',
        views.report_list_by_attr, name='list_attr'),
    url(r'^(?P<leaf_type>unsafe|safe|unknown)/(?P<report_id>[0-9]+)/$', views.report_leaf, name='leaf'),
    url(r'^unsafe/(?P<report_id>[0-9]+)/etv/$', views.report_etv_full, name='etv'),
    url(r'^component/(?P<report_id>[0-9]+)/unknowns/(?P<component_id>[0-9]+)/$',
        views.report_unknowns, name='unknowns'),
    url(r'^component/(?P<report_id>[0-9]+)/unknowns/(?P<component_id>[0-9]+)/problem/(?P<problem_id>[0-9]+)/$',
        views.report_unknowns_by_problem, name='unknowns_problem'),
    url(r'^comparison/(?P<job1_id>[0-9]+)/(?P<job2_id>[0-9]+)/$', views.jobs_comparison, name='comparison'),
    url(r'^download-error-trace/(?P<report_id>[0-9]+)/$', views.download_error_trace, name='download_error_trace'),

    url(r'^upload/$', views.upload_report),
    url(r'^ajax/get_source/$', views.get_source_code),
    url(r'^ajax/fill_compare_cache/$', views.fill_compare_cache),
    url(r'^ajax/get_compare_jobs_data/$', views.get_compare_jobs_data),
    url(r'^component/(?P<report_id>[0-9]+)/download_files/$', views.download_report_files, name='download_files'),
]
