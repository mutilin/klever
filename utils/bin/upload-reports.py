#!/usr/bin/env python3
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

import os

from utils.utils import get_args_parser, Session

parser = get_args_parser('Upload ZIP archive with reports for verificaiton job.')
parser.add_argument('job', help='Verification job identifier or its name.')
parser.add_argument('--archive', help='ZIP archive name.', required=True)
args = parser.parse_args()

if not os.path.exists(args.archive):
    raise FileNotFoundError('ZIP archive with reports "{0}" does not exist'.format(args.archive))

with Session(args) as session:
    session.upload_reports(args.job, args.archive)

print('ZIP archive with reports "{0}" was successfully uploaded for verificaiton job "{1}"'
      .format(args.archive, args.job))
