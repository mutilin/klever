from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext_lazy as _
from Omega.tableHead import Header
from marks.models import *


MARK_TITLES = {
    'mark_num': '№',
    'change_kind': _('Change kind'),
    'verdict': _("Verdict"),
    'result': _('Similarity'),
    'status': _('Status'),
    'author': _('Author'),
    'report': _('Report'),
    'job': _('Job'),
    'format': _('Psi format'),
    'number': '№',
    'num_of_links': _('Number of links'),
}

STATUS_COLOR = {
    '0': '#D11919',
    '1': '#FF8533',
    '2': '#FF8533',
    '3': '#00B800',
}

UNSAFE_COLOR = {
    '0': '#A739CC',
    '1': '#D11919',
    '2': '#D11919',
    '3': '#FF8533',
    '4': '#D11919',
    '5': '#000000',
}

SAFE_COLOR = {
    '0': '#A739CC',
    '1': '#FF8533',
    '2': '#D11919',
    '3': '#D11919',
    '4': '#000000',
}


def result_color(result):
    if 0 < result <= 0.33:
        return '#E60000'
    elif 0.33 < result <= 0.66:
        return '#CC7A29'
    elif 0.66 < result <= 1:
        return '#00CC66'
    return None


class MarkChangesTable(object):

    def __init__(self, mark, changes):
        self.columns = ['report', 'change_kind', 'verdict']
        if isinstance(mark, MarkUnsafe):
            self.columns.append('result')
        elif not isinstance(mark, MarkSafe):
            return
        self.columns.extend(['status', 'author', 'job', 'format'])
        self.mark = mark
        self.changes = changes
        self.attr_values_data = self.__add_attrs()
        self.header = Header(self.columns, MARK_TITLES).struct
        if isinstance(mark, MarkUnsafe):
            self.values = self.__get_unsafe_values()
        else:
            self.values = self.__get_safe_values()

    def __add_attrs(self):
        data = {}
        for report in self.changes:
            for attr in report.attr.all():
                if attr.name.name not in data:
                    data[attr.name.name] = {}
                data[attr.name.name][report] = attr.value
        columns = []
        for name in sorted(data):
            columns.append(name)
        values_data = {}
        for report in self.changes:
            values_data[report] = {}
            for col in columns:
                cell_val = '-'
                if report in data[col]:
                    cell_val = data[col][report]
                values_data[report][col] = cell_val
        self.columns.extend(columns)
        return values_data

    def __get_unsafe_values(self):

        def colored_change(v1, v2, col1=None, col2=None):
            if col1 is not None and col2 is not None:
                return '<span style="color:%s">%s</span> ' \
                       '-> <span style="color:%s">%s</span>' % \
                       (col1, v1, col2, v2)
            return '<span>%s</span> -> <span>%s</span>' % (v1, v2)

        def get_verdict_change(rep):

            if all(x in self.changes[rep] for x in ['verdict1', 'verdict2']):
                tmp_unsafe = ReportUnsafe()
                tmp_unsafe.verdict = self.changes[rep]['verdict1']
                val1 = tmp_unsafe.get_verdict_display()
                if self.changes[rep]['verdict1'] == \
                        self.changes[rep]['verdict2']:
                    return '<span style="color:%s">%s</span>' % (
                        UNSAFE_COLOR[self.changes[rep]['verdict1']], val1)
                tmp_unsafe.verdict = self.changes[rep]['verdict2']
                val2 = tmp_unsafe.get_verdict_display()
                return colored_change(
                    val1, val2, UNSAFE_COLOR[self.changes[rep]['verdict1']],
                    UNSAFE_COLOR[self.changes[rep]['verdict2']])
            return '<span style="color:%s">%s</span>' % (
                UNSAFE_COLOR[rep.verdict],
                rep.get_verdict_display()
            )

        def get_status_change():
            v_set = self.mark.markunsafehistory_set.all().order_by('-version')
            last_version = v_set[0]
            try:
                prev_version = v_set[1]
            except IndexError:
                return '<span style="color:%s">%s</span>' % (
                    STATUS_COLOR[last_version.status],
                    last_version.get_status_display()
                )
            if prev_version.status == last_version.status:
                return '<span style="color:%s">%s</span>' % (
                    STATUS_COLOR[last_version.status],
                    last_version.get_status_display()
                )
            return colored_change(
                prev_version.get_status_display(),
                last_version.get_status_display(),
                STATUS_COLOR[prev_version.status],
                STATUS_COLOR[last_version.status]
            )

        def get_result_change(rep):
            if all(x in self.changes[rep] for x in ['result1', 'result2']):
                return colored_change(
                    "{:.0%}".format(self.changes[rep]['result1']),
                    "{:.0%}".format(self.changes[rep]['result2']),
                    result_color(self.changes[rep]['result1']),
                    result_color(self.changes[rep]['result2'])
                )
            elif 'result1' in self.changes[rep]:
                return '<span style="color:%s">%s</span>' % (
                    result_color(self.changes[rep]['result1']),
                    "{:.0%}".format(self.changes[rep]['result1']))
            elif 'result2' in self.changes[rep]:
                return '<span style="color:%s">%s</span>' % (
                    result_color(self.changes[rep]['result2']),
                    "{:.0%}".format(self.changes[rep]['result2']))
            else:
                return '-'

        values = []

        cnt = 0
        for report in self.changes:
            cnt += 1
            values_str = []
            for col in self.columns:
                val = '-'
                color = None
                href = None
                try:
                    report_mark = self.mark.markunsafereport_set.get(
                        report=report)
                except ObjectDoesNotExist:
                    report_mark = None
                if col in self.attr_values_data[report]:
                    val = self.attr_values_data[report][col]
                elif col == 'report':
                    val = cnt
                    href = reverse('reports:leaf', args=['unsafe', report.pk])
                elif col == 'verdict':
                    val = get_verdict_change(report)
                elif col == 'status':
                    val = get_status_change()
                elif col == 'change_kind':
                    if self.changes[report]['kind'] == '=':
                        val = _("Changed")
                        color = '#CC7A29'
                    elif self.changes[report]['kind'] == '+':
                        val = _("New")
                        color = '#008F00'
                    elif self.changes[report]['kind'] == '-':
                        val = _("Deleted")
                        color = '#B80000'
                elif col == 'result':
                    val = get_result_change(report)
                elif col == 'author':
                    if report_mark is not None:
                        val = "%s %s" % (
                            report_mark.mark.author.extended.last_name,
                            report_mark.mark.author.extended.first_name
                        )
                        href = reverse('users:show_profile',
                                       args=[report_mark.mark.author.pk])
                elif col == 'job':
                    val = report.root.job.name
                    href = reverse('jobs:job', args=[report.root.job.pk])
                elif col == 'format':
                    val = report.root.job.format
                values_str.append({
                    'value': val,
                    'color': color,
                    'href': href
                })
            values.append(values_str)
        return values

    def __get_safe_values(self):

        def colored_change(v1, v2, col1=None, col2=None):
            if col1 is not None and col2 is not None:
                return '<span style="color:%s">%s</span> ' \
                       '-> <span style="color:%s">%s</span>' % \
                       (col1, v1, col2, v2)
            return '<span>%s</span> -> <span>%s</span>' % (v1, v2)

        def get_verdict_change(rep):
            if all(x in self.changes[rep] for x in ['verdict1', 'verdict2']):
                tmp_safe = ReportSafe()
                tmp_safe.verdict = self.changes[rep]['verdict1']
                val1 = tmp_safe.get_verdict_display()
                if self.changes[rep]['verdict1'] == \
                        self.changes[rep]['verdict2']:
                    return '<span style="color:%s">%s</span>' % (
                        SAFE_COLOR[self.changes[rep]['verdict1']], val1)
                tmp_safe.verdict = self.changes[rep]['verdict2']
                val2 = tmp_safe.get_verdict_display()
                return colored_change(
                    val1, val2, SAFE_COLOR[self.changes[rep]['verdict1']],
                    SAFE_COLOR[self.changes[rep]['verdict2']])
            return '<span style="color:%s">%s</span>' % (
                SAFE_COLOR[rep.verdict],
                rep.get_verdict_display()
            )

        def get_status_change():
            v_set = self.mark.marksafehistory_set.all().order_by('-version')
            last_version = v_set[0]
            try:
                prev_version = v_set[1]
            except IndexError:
                return '<span style="color:%s">%s</span>' % (
                    STATUS_COLOR[last_version.status],
                    last_version.get_status_display()
                )
            if prev_version.status == last_version.status:
                return '<span style="color:%s">%s</span>' % (
                    STATUS_COLOR[last_version.status],
                    last_version.get_status_display()
                )
            return colored_change(
                prev_version.get_status_display(),
                last_version.get_status_display(),
                STATUS_COLOR[prev_version.status],
                STATUS_COLOR[last_version.status]
            )

        values = []

        cnt = 0
        for report in self.changes:
            cnt += 1
            values_str = []
            for col in self.columns:
                val = '-'
                color = None
                href = None
                try:
                    report_mark = self.mark.marksafereport_set.get(
                        report=report)
                except ObjectDoesNotExist:
                    continue
                if col in self.attr_values_data[report]:
                    val = self.attr_values_data[report][col]
                elif col == 'report':
                    val = cnt
                    href = reverse('reports:leaf', args=['safe', report.pk])
                elif col == 'verdict':
                    val = get_verdict_change(report)
                elif col == 'status':
                    val = get_status_change()
                elif col == 'change_kind':
                    if self.changes[report]['kind'] == '=':
                        val = _("Updated")
                        color = '#CC7A29'
                    elif self.changes[report]['kind'] == '+':
                        val = _("Created")
                        color = '#008F00'
                    elif self.changes[report]['kind'] == '-':
                        val = _("Deleted")
                        color = '#B80000'
                elif col == 'author':
                    val = "%s %s" % (
                        report_mark.mark.author.extended.last_name,
                        report_mark.mark.author.extended.first_name
                    )
                    href = reverse('users:show_profile',
                                   args=[report_mark.mark.author.pk])
                elif col == 'job':
                    val = report.root.job.name
                    href = reverse('jobs:job', args=[report.root.job.pk])
                elif col == 'format':
                    val = report.root.job.format
                values_str.append({
                    'value': val,
                    'color': color,
                    'href': href
                })
            values.append(values_str)
        return values


# Table data for showing links between the specified mark and reports
class MarkReportsTable(object):
    def __init__(self, mark):
        self.columns = ['report', 'verdict']
        self.type = 'safe'
        if isinstance(mark, MarkUnsafe):
            self.columns.append('result')
            self.type = 'unsafe'
        elif not isinstance(mark, MarkSafe):
            return
        self.columns.extend(['status', 'author', 'job', 'format'])
        self.mark = mark
        self.attr_values_data, self.reports = self.__add_attrs()
        self.header = Header(self.columns, MARK_TITLES).struct
        self.values = self.__get_unsafe_values()

    def __add_attrs(self):
        data = {}
        if self.type == 'unsafe':
            m_r_set = self.mark.markunsafereport_set.all().order_by('-result')
        else:
            m_r_set = self.mark.marksafereport_set.all()
        reports = []
        for mark_report in m_r_set:
            report = mark_report.report
            for attr in report.attr.all():
                if attr.name.name not in data:
                    data[attr.name.name] = {}
                data[attr.name.name][report] = attr.value
            reports.append(report)

        columns = []
        for name in sorted(data):
            columns.append(name)

        values_data = {}
        for report in reports:
            values_data[report] = {}
            for col in columns:
                cell_val = '-'
                if report in data[col]:
                    cell_val = data[col][report]
                values_data[report][col] = cell_val
        self.columns.extend(columns)
        return values_data, reports

    def __get_unsafe_values(self):
        values = []
        cnt = 0
        for report in self.reports:
            cnt += 1
            values_str = []
            for col in self.columns:
                try:
                    if self.type == 'unsafe':
                        report_mark = self.mark.markunsafereport_set.get(
                            report=report)
                    else:
                        report_mark = self.mark.marksafereport_set.get(
                            report=report)
                except ObjectDoesNotExist:
                    continue
                val = '-'
                color = None
                href = None
                if col in self.attr_values_data[report]:
                    val = self.attr_values_data[report][col]
                elif col == 'report':
                    val = cnt
                    href = reverse('reports:leaf', args=[self.type, report.pk])
                elif col == 'verdict':
                    val = report.get_verdict_display()
                    color = UNSAFE_COLOR[report.verdict]
                elif col == 'status':
                    if self.type == 'unsafe':
                        l_v = self.mark.markunsafehistory_set.get(
                            version=self.mark.version)
                    else:
                        l_v = self.mark.marksafehistory_set.get(
                            version=self.mark.version)
                    val = l_v.get_status_display()
                    color = STATUS_COLOR[l_v.status]
                elif col == 'result':
                    val = "{:.0%}".format(report_mark.result)
                    color = result_color(report_mark.result)
                elif col == 'author':
                    val = "%s %s" % (
                        report_mark.mark.author.extended.last_name,
                        report_mark.mark.author.extended.first_name
                    )
                    href = reverse('users:show_profile',
                                   args=[report_mark.mark.author.pk])
                elif col == 'job':
                    val = report.root.job.name
                    href = reverse('jobs:job', args=[report.root.job.pk])
                elif col == 'format':
                    val = report.root.job.format
                values_str.append({'value': val, 'href': href, 'color': color})
            values.append(values_str)
        return values


# Table data for showing links between the specified report and marks
class ReportMarkTable(object):
    def __init__(self, report):
        self.report = report
        self.type = 'safe'
        self.columns = ['number', 'verdict']
        if isinstance(report, ReportUnsafe):
            self.columns.append('result')
            self.type = 'unsafe'
        elif not isinstance(report, ReportSafe):
            return
        self.columns.extend(['status', 'author'])
        self.header = Header(self.columns, MARK_TITLES).struct
        self.values = self.__get_values()

    def __get_values(self):
        value_data = []
        if isinstance(self.report, ReportUnsafe):
            mr_set = self.report.markunsafereport_set.all().order_by('-result')
        else:
            mr_set = self.report.marksafereport_set.all()
        cnt = 0
        for mark_rep in mr_set:
            cnt += 1
            values_row = []
            for col in self.columns:
                value = '-'
                href = None
                color = None
                if col == 'number':
                    value = cnt
                    href = reverse('marks:edit_mark',
                                   args=[self.type, mark_rep.mark.pk])
                elif col == 'verdict':
                    value = mark_rep.mark.get_verdict_display()
                    if self.type == 'unsafe':
                        color = UNSAFE_COLOR[mark_rep.mark.verdict]
                    else:
                        color = SAFE_COLOR[mark_rep.mark.verdict]
                elif col == 'result':
                    value = "{:.0%}".format(mark_rep.result)
                    color = result_color(mark_rep.result)
                elif col == 'status':
                    value = mark_rep.mark.get_status_display()
                    color = STATUS_COLOR[mark_rep.mark.status]
                elif col == 'author':
                    if mark_rep.mark.author is not None:
                        value = "%s %s" % (
                            mark_rep.mark.author.extended.last_name,
                            mark_rep.mark.author.extended.first_name
                        )
                        href = reverse(
                            'users:show_profile',
                            args=[mark_rep.mark.author.pk]
                        )
                values_row.append({
                    'value': value, 'href': href, 'color': color
                })
            value_data.append(values_row)
        return value_data


class MarkListTable(object):
    def __init__(self, marks_type):
        self.columns = ['mark_num', 'verdict']
        if marks_type == 'unsafe':
            self.columns.append('result')
        elif marks_type != 'safe':
            return
        self.type = marks_type
        self.columns.extend(['status', 'author', 'report', 'job', 'format'])
        self.attr_values_data, self.reports = self.__add_attrs()
        self.header = Header(self.columns, MARK_TITLES).struct
        self.values = self.__get_values()

    def __add_attrs(self):
        data = {}
        if self.type == 'unsafe':
            markreport_set = MarkUnsafeReport.objects.all().order_by('-result')
        else:
            markreport_set = MarkSafeReport.objects.all()
        reports = []
        for mark_report in markreport_set:
            for attr in mark_report.report.attr.all():
                if attr.name.name not in data:
                    data[attr.name.name] = {}
                data[attr.name.name][mark_report] = attr.value
            reports.append(mark_report)

        columns = []
        for name in sorted(data):
            columns.append(name)

        values_data = {}
        for mark_report in reports:
            values_data[mark_report] = {}
            for col in columns:
                cell_val = '-'
                if mark_report in data[col]:
                    cell_val = data[col][mark_report]
                values_data[mark_report][col] = cell_val
        self.columns.extend(columns)
        return values_data, reports

    def __get_values(self):
        values = []

        cnt_data = {}
        cnt_marks = 0
        cnt_reports = 0
        for m_rep in self.reports:
            if m_rep.mark not in cnt_data:
                cnt_marks += 1
                cnt_data[m_rep.mark] = cnt_marks
            if m_rep.report not in cnt_data:
                cnt_reports += 1
                cnt_data[m_rep.report] = cnt_reports
        for m_rep in self.reports:
            values_str = []
            for col in self.columns:
                val = '-'
                color = None
                href = None
                if col in self.attr_values_data[m_rep]:
                    val = self.attr_values_data[m_rep][col]
                elif col == 'mark_num':
                    val = cnt_data[m_rep.mark]
                    href = reverse(
                        'marks:edit_mark',
                        args=[self.type, m_rep.mark.pk]
                    )
                elif col == 'report':
                    val = cnt_data[m_rep.report]
                    href = reverse('reports:leaf',
                                   args=[self.type, m_rep.report.pk])
                elif col == 'verdict':
                    val = m_rep.mark.get_verdict_display()
                    if self.type == 'safe':
                        color = SAFE_COLOR[m_rep.mark.verdict]
                    else:
                        color = UNSAFE_COLOR[m_rep.mark.verdict]
                elif col == 'status':
                    val = m_rep.mark.get_status_display()
                    color = STATUS_COLOR[m_rep.mark.status]
                elif col == 'result':
                    val = "{:.0%}".format(float(m_rep.result))
                elif col == 'author':
                    val = "%s %s" % (
                        m_rep.mark.author.extended.last_name,
                        m_rep.mark.author.extended.first_name
                    )
                    href = reverse('users:show_profile',
                                   args=[m_rep.mark.author.pk])
                elif col == 'job':
                    val = m_rep.report.root.job.name
                    href = reverse('jobs:job', args=[m_rep.report.root.job.pk])
                elif col == 'format':
                    val = m_rep.report.root.job.format
                values_str.append({'color': color, 'value': val, 'href': href})
            values.append(values_str)
        return values


class AllMarksList(object):

    def __init__(self, marks_type):
        self.columns = ['mark_num', 'num_of_links', 'verdict']
        if marks_type != 'unsafe' and marks_type != 'safe':
            return
        self.type = marks_type
        self.columns.extend(['status', 'author', 'format'])
        self.attr_values_data, self.marks = self.__add_attrs()
        self.header = Header(self.columns, MARK_TITLES).struct
        self.values = self.__get_values()

    def __add_attrs(self):
        data = {}
        marks = []
        if self.type == 'unsafe':
            for mark in MarkUnsafe.objects.all():
                last_v = mark.markunsafehistory_set.get(version=mark.version)
                for attr in last_v.markunsafeattr_set.all():
                    if attr.is_compare:
                        if attr.attr.name.name not in data:
                            data[attr.attr.name.name] = {}
                        data[attr.attr.name.name][mark] = attr.attr.value
                marks.append(mark)
        else:
            for mark in MarkSafe.objects.all():
                last_v = mark.marksafehistory_set.get(version=mark.version)
                for attr in last_v.marksafeattr_set.all():
                    if attr.is_compare:
                        if attr.attr.name.name not in data:
                            data[attr.attr.name.name] = {}
                        data[attr.attr.name.name][mark] = attr.attr.value
                marks.append(mark)

        columns = []
        for name in sorted(data):
            columns.append(name)

        values_data = {}
        for mark in marks:
            values_data[mark] = {}
            for col in columns:
                cell_val = '-'
                if mark in data[col]:
                    cell_val = data[col][mark]
                values_data[mark][col] = cell_val
        self.columns.extend(columns)
        return values_data, marks

    def __get_values(self):
        values = []

        cnt = 0
        for mark in self.marks:
            cnt += 1
            values_str = []
            for col in self.columns:
                val = '-'
                color = None
                href = None
                if col in self.attr_values_data[mark]:
                    val = self.attr_values_data[mark][col]
                elif col == 'mark_num':
                    val = cnt
                    href = reverse('marks:edit_mark', args=[self.type, mark.pk])
                elif col == 'num_of_links':
                    if self.type == 'unsafe':
                        val = len(mark.markunsafereport_set.all())
                    else:
                        val = len(mark.marksafereport_set.all())
                elif col == 'verdict':
                    val = mark.get_verdict_display()
                    if self.type == 'safe':
                        color = SAFE_COLOR[mark.verdict]
                    else:
                        color = UNSAFE_COLOR[mark.verdict]
                elif col == 'status':
                    val = mark.get_status_display()
                    color = STATUS_COLOR[mark.status]
                elif col == 'author':
                    val = "%s %s" % (
                        mark.author.extended.last_name,
                        mark.author.extended.first_name
                    )
                    href = reverse('users:show_profile', args=[mark.author.pk])
                elif col == 'format':
                    val = mark.format
                values_str.append({'color': color, 'value': val, 'href': href})
            values.append(values_str)
        return values


class MarkAttrTable(object):

    def __init__(self, report=None, mark_version=None):
        self.report = report
        self.mark_version = mark_version
        self.header, self.values = self.__self_attrs()

    def __self_attrs(self):
        columns = []
        values = []
        if isinstance(self.mark_version, MarkUnsafeHistory):
            for attr in self.mark_version.markunsafeattr_set.all().order_by(
                    'attr__name__name'):
                columns.append(attr.attr.name.name)
                values.append(
                    (attr.attr.name.name, attr.attr.value, attr.is_compare)
                )
        elif isinstance(self.mark_version, MarkSafeHistory):
            for attr in self.mark_version.marksafeattr_set.all().order_by(
                    'attr__name__name'):
                columns.append(attr.attr.name.name)
                values.append(
                    (attr.attr.name.name, attr.attr.value, attr.is_compare)
                )
        else:
            for attr in self.report.attr.all().order_by('name__name'):
                columns.append(attr.name.name)
                values.append((attr.name.name, attr.value, True))
        return Header(columns, {}).struct, values


class MarkData(object):
    def __init__(self, mark_type, mark_version=None):
        self.type = mark_type
        self.mark_version = mark_version
        self.verdicts = self.__verdict_info()
        self.statuses = self.__status_info()
        self.comparison, self.compare_desc = self.__functions('compare')
        self.convertion, self.convert_desc = self.__functions('convert')

    def __verdict_info(self):
        verdicts = []
        if self.type == 'unsafe':
            for verdict in MARK_UNSAFE:
                verdict_data = {
                    'title': verdict[1],
                    'value': verdict[0],
                    'checked': False,
                    'color': UNSAFE_COLOR[verdict[0]]
                }
                if (isinstance(self.mark_version, MarkUnsafeHistory) and
                        verdict_data['value'] == self.mark_version.verdict) or \
                        (not isinstance(self.mark_version, MarkUnsafeHistory)
                         and verdict_data['value'] == '0'):
                    verdict_data['checked'] = True
                verdicts.append(verdict_data)
        elif self.type == 'safe':
            for verdict in MARK_SAFE:
                verdict_data = {
                    'title': verdict[1],
                    'value': verdict[0],
                    'checked': False,
                    'color': SAFE_COLOR[verdict[0]]
                }
                if (isinstance(self.mark_version, MarkSafeHistory) and
                        verdict_data['value'] == self.mark_version.verdict) or \
                        (not isinstance(self.mark_version, MarkSafeHistory)
                         and verdict_data['value'] == '0'):
                    verdict_data['checked'] = True
                verdicts.append(verdict_data)
        return verdicts

    def __status_info(self):
        statuses = []
        for verdict in MARK_STATUS:
            status_data = {
                'title': verdict[1],
                'value': verdict[0],
                'checked': False,
                'color': STATUS_COLOR[verdict[0]]
            }
            if ((isinstance(self.mark_version, MarkUnsafeHistory) or
                isinstance(self.mark_version, MarkSafeHistory)) and
                    status_data['value'] == self.mark_version.status) or \
                    (self.mark_version is None and status_data['value'] == '0'):
                status_data['checked'] = True
            statuses.append(status_data)
        return statuses

    def __functions(self, func_type='compare'):
        if self.type != 'unsafe':
            return [], None
        functions = []
        def_func = None
        if func_type == 'compare':
            selected_description = None
            try:
                def_func = MarkDefaultFunctions.objects.all()[0].compare
            except IndexError:
                pass

            for f in MarkUnsafeCompare.objects.all().order_by('name'):
                func_data = {
                    'name': f.name,
                    'selected': False,
                    'value': f.pk,
                }
                if isinstance(self.mark_version, MarkUnsafeHistory):
                    if self.mark_version.function == f:
                        func_data['selected'] = True
                        selected_description = f.description
                elif (not isinstance(self.mark_version, MarkUnsafe) and
                        def_func == f):
                    func_data['selected'] = True
                    selected_description = f.description
                functions.append(func_data)
        elif func_type == 'convert':
            if self.mark_version is not None:
                return [], None

            selected_description = None
            try:
                def_func = MarkDefaultFunctions.objects.all()[0].convert
            except IndexError:
                pass

            for f in MarkUnsafeConvert.objects.all().order_by('name'):
                func_data = {
                    'name': f.name,
                    'selected': False,
                    'value': f.pk,
                }
                if def_func == f:
                    func_data['selected'] = True
                    selected_description = f.description
                functions.append(func_data)
        else:
            return [], None
        return functions, selected_description
