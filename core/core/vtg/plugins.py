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

import core.components


class Plugin(core.components.Component):
    depend_on_requirement = True

    def run(self):
        in_abstract_task_desc_file = os.path.relpath(
            os.path.join(self.conf['main working directory'], self.conf['in abstract task desc file']))
        self.logger.info(
            'Get abstract verification task description from file "{0}"'.format(in_abstract_task_desc_file))
        with open(in_abstract_task_desc_file, encoding='utf8') as fp:
            self.abstract_task_desc = json.load(fp)

        self.logger.info('Start processing of abstract verification task "{0}"'.format(self.abstract_task_desc['id']))
        core.components.Component.run(self)

        out_abstract_task_desc_file = os.path.relpath(
            os.path.join(self.conf['main working directory'], self.conf['out abstract task desc file']))
        self.logger.info(
            'Put modified abstract verification task description to file "{0}"'.format(out_abstract_task_desc_file))
        with open(out_abstract_task_desc_file, 'w', encoding='utf8') as fp:
            json.dump(self.abstract_task_desc, fp, ensure_ascii=False, sort_keys=True, indent=4)

        self.logger.info('Finish processing of abstract verification task "{0}"'.format(self.abstract_task_desc['id']))
