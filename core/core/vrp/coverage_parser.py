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
import json
import os
import shutil

import core.utils


class LCOV:
    NEW_FILE_PREFIX = "TN:"
    EOR_PREFIX = "end_of_record"
    FILENAME_PREFIX = "SF:"
    LINE_PREFIX = "DA:"
    FUNCTION_PREFIX = "FNDA:"
    FUNCTION_NAME_PREFIX = "FN:"
    PARIALLY_ALLOWED_EXT = ('.c', '.i', '.c.aux')

    def __init__(self, logger, coverage_file, storage_src_tree, ext_modules_dir, work_src_tree, search_dirs, main_work_dir, completeness,
                 coverage_id, coverage_info_dir):
        # Public
        self.logger = logger
        self.coverage_file = coverage_file
        self.storage_src_tree = storage_src_tree
        self.work_src_tree = work_src_tree
        self.search_dirs = search_dirs
        self.main_work_dir = main_work_dir
        self.completeness = completeness
        self.coverage_info_dir = coverage_info_dir
        self.ext_modules_dir = ext_modules_dir

        self.arcnames = {}
        self.logger.debug("Search dirs are {0}".format(self.search_dirs))
        self.logger.debug("Work src tree is {0}".format(self.work_src_tree))
        self.logger.debug("Work dir is {0}".format(self.main_work_dir))
        self.logger.debug("Ext modules dir is {0}".format(self.ext_modules_dir))

        # Sanity checks
        if self.completeness not in ('full', 'partial', 'lightweight', 'none', None):
            raise NotImplementedError("Coverage type {!r} is not supported".format(self.completeness))

        # Import coverage
        try:
            if self.completeness in ('full', 'partial', 'lightweight'):
                self.coverage_info = self.parse()

                with open(coverage_id, 'w', encoding='utf-8') as fp:
                    json.dump(self.coverage_info, fp, ensure_ascii=True, sort_keys=True, indent=4)

                coverage = {}
                self.add_to_coverage(coverage, self.coverage_info)
                with open('coverage.json', 'w', encoding='utf-8') as fp:
                    json.dump(LCOV.get_coverage(coverage), fp, ensure_ascii=True,
                              sort_keys=True, indent=4)
        except Exception as e:
            self.logger.exception('Could not parse coverage')

    def parse(self):
        dir_map = [('source files', self.work_src_tree),
                   ('specifications', os.path.join(self.main_work_dir, 'job', 'root')),
                   ('generated models', self.main_work_dir)]

        if self.ext_modules_dir:
            dir_map.insert(1, ('source files', self.ext_modules_dir))

        ignore_file = False

        if not os.path.isfile(self.coverage_file):
            raise Exception('There is no coverage file {0}'.format(self.coverage_file))

        # Gettings dirs, that should be excluded.
        excluded_dirs = set()
        if self.completeness in ('partial', 'lightweight'):
            with open(self.coverage_file, encoding='utf-8') as fp:
                # Build map, that contains dir as key and list of files in the dir as value
                all_files = {}
                for line in fp:
                    line = line.rstrip('\n')
                    if line.startswith(self.FILENAME_PREFIX):
                        file_name = line[len(self.FILENAME_PREFIX):]
                        if os.path.isfile(file_name):
                            dir, file = os.path.split(file_name)
                            if dir.startswith(self.storage_src_tree):
                                dir = os.path.join('/', os.path.relpath(dir, self.storage_src_tree))
                            all_files.setdefault(dir, [])
                            if file_name.startswith(self.storage_src_tree):
                                file_name = os.path.join('/', os.path.relpath(file_name, self.storage_src_tree))
                            all_files[dir].append(file)

                for dir, files in all_files.items():
                    # Lightweight coverage keeps only source code dirs.
                    if self.completeness == 'lightweight' \
                            and not dir.startswith(self.work_src_tree)\
                            and self.ext_modules_dir and dir.startswith(self.ext_modules_dir):
                        self.logger.debug('Excluded {0}'.format(dir))
                        excluded_dirs.add(dir)
                        continue
                    # Partial coverage keeps only dirs, that contains source files.
                    for file in files:
                        if file.endswith('.c') or file.endswith('.c.aux'):
                            break
                    else:
                        excluded_dirs.add(dir)

        # Parsing coverage file
        coverage_info = {}
        with open(self.coverage_file, encoding='utf-8') as fp:
            count_covered_functions = None
            for line in fp:
                line = line.rstrip('\n')

                if ignore_file and not line.startswith(self.FILENAME_PREFIX):
                    continue

                if line.startswith(self.NEW_FILE_PREFIX):
                    # Clean
                    file_name = None
                    covered_lines = {}
                    function_to_line = {}
                    covered_functions = {}
                    count_covered_functions = 0
                elif line.startswith(self.FILENAME_PREFIX):
                    # Get file name, determine his directory and determine, should we ignore this
                    init_file_name = line[len(self.FILENAME_PREFIX):]
                    if not os.path.isfile(init_file_name):
                        ignore_file = True
                        continue
                    if init_file_name.startswith(self.storage_src_tree):
                        file_name = os.path.join('/', os.path.relpath(init_file_name, self.storage_src_tree))
                    else:
                        file_name = init_file_name
                    if not any(map(lambda prefix: file_name.startswith(prefix), excluded_dirs)):
                        for dest, src in dir_map:
                            if file_name.startswith(src):
                                if dest == 'generated models':
                                    copy_file_name = os.path.join(self.coverage_info_dir, os.path.relpath(file_name, src))
                                    if not os.path.exists(os.path.dirname(copy_file_name)):
                                        os.makedirs(os.path.dirname(copy_file_name))
                                    shutil.copy(file_name, copy_file_name)
                                    file_name = copy_file_name
                                    new_file_name = os.path.join(dest, os.path.basename(file_name))
                                else:
                                    new_file_name = os.path.join(dest, os.path.relpath(file_name, src))
                                ignore_file = False
                                break
                        # This "else" corresponds "for"
                        else:
                            new_file_name = core.utils.make_relative_path(self.search_dirs, file_name)
                            if new_file_name == file_name:
                                ignore_file = True
                                continue
                            else:
                                ignore_file = False
                            new_file_name = os.path.join('specifications', new_file_name)

                        self.arcnames[init_file_name] = new_file_name
                        old_file_name, file_name = init_file_name, new_file_name
                    else:
                        ignore_file = True
                elif line.startswith(self.LINE_PREFIX):
                    # Coverage of the specified line
                    splts = line[len(self.LINE_PREFIX):].split(',')
                    covered_lines[int(splts[0])] = int(splts[1])
                elif line.startswith(self.FUNCTION_NAME_PREFIX):
                    # Mapping of the function name to the line number
                    splts = line[len(self.FUNCTION_NAME_PREFIX):].split(',')
                    function_to_line.setdefault(splts[1], [])
                    function_to_line[splts[1]] = int(splts[0])
                elif line.startswith(self.FUNCTION_PREFIX):
                    # Coverage of the specified function
                    splts = line[len(self.FUNCTION_PREFIX):].split(',')
                    if splts[0] == "0":
                        continue
                    covered_functions[function_to_line[splts[1]]] = int(splts[0])
                    count_covered_functions += 1
                elif line.startswith(self.EOR_PREFIX):
                    # End coverage for the specific file

                    # Add not covered functions
                    covered_functions.update({line: 0 for line in set(function_to_line.values())
                                             .difference(set(covered_functions.keys()))})

                    coverage_info.setdefault(file_name, [])
                    coverage_info[file_name].append({
                        'file name': old_file_name,
                        'arcname': file_name,
                        'total functions': len(function_to_line),
                        'covered lines': covered_lines,
                        'covered functions': covered_functions
                    })

        return coverage_info

    @staticmethod
    def add_to_coverage(merged_coverage_info, coverage_info):
        for file_name in coverage_info:
            merged_coverage_info.setdefault(file_name, {
                'total functions': coverage_info[file_name][0]['total functions'],
                'covered lines': {},
                'covered functions': {}
            })

            for coverage in coverage_info[file_name]:
                for type in ('covered lines', 'covered functions'):
                    for line, value in coverage[type].items():
                        merged_coverage_info[file_name][type].setdefault(line, 0)
                        merged_coverage_info[file_name][type][line] += value

    @staticmethod
    def get_coverage(merged_coverage_info):

        # Map combined coverage to the required format
        line_coverage = {}
        function_coverage = {}
        function_statistics = {}

        for file_name in list(merged_coverage_info.keys()):
            for line, value in merged_coverage_info[file_name]['covered lines'].items():
                line_coverage.setdefault(value, {})
                line_coverage[value].setdefault(file_name, [])
                line_coverage[value][file_name].append(int(line))

            for line, value in merged_coverage_info[file_name]['covered functions'].items():
                function_coverage.setdefault(value, {})
                function_coverage[value].setdefault(file_name, [])
                function_coverage[value][file_name].append(int(line))

            function_statistics[file_name] = [len(merged_coverage_info[file_name]['covered functions']),
                                              merged_coverage_info[file_name]['total functions']]
            del merged_coverage_info[file_name]

        # Merge contiguous covered lines into a range
        for key, value in line_coverage.items():
            for file_name, lines in value.items():
                line_coverage[key][file_name] = LCOV.__build_ranges(lines)

        return {
            'line coverage': [[key, value] for key, value in line_coverage.items()],
            'function coverage': {
                'statistics': function_statistics,
                'coverage': [[key, value] for key, value in function_coverage.items()]
                }
        }

    @staticmethod
    def __build_ranges(lines):
        if not lines:
            return []
        res = []
        prev = 0
        lines = sorted(lines)
        for i in range(1, len(lines)):
            if lines[i] != lines[i-1] + 1:
                # The sequence is broken.
                if i - 1 != prev:
                    # There is more than one line in the sequence. .
                    if i - 2 == prev:
                        # There is more than two lines in the sequence. Add the range.
                        res.append(lines[prev])
                        res.append(lines[i - 1])
                    else:
                        # Otherwise, add these lines separately.
                        res.append([lines[prev], lines[i-1]])
                else:
                    # Just add a single non-sequence line.
                    res.append(lines[prev])
                prev = i

        # This step is the same as in the loop body.
        if prev != len(lines) - 1:
            if prev == len(lines) - 2:
                res.append(lines[prev])
                res.append(lines[-1])
            else:
                res.append([lines[prev], lines[-1]])
        else:
            res.append(lines[prev])

        return res
