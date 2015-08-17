from django.utils.translation import ugettext_lazy as _

FORMAT = 1

JOB_CLASSES = (
    ('0', _('Verification of Linux kernel modules')),
    ('1', _('Verification of commits in Linux kernel Git repositories')),
    ('2', _('Verification of C programs')),
)

JOB_ROLES = (
    ('0', _('No access')),
    ('1', _('Observer')),
    ('2', _('Expert')),
    ('3', _('Observer and Operator')),
    ('4', _('Expert and Operator')),
)

# Default view of the table
JOB_DEF_VIEW = {
    'columns': ['name', 'role', 'author', 'date', 'status', 'unsafe', 'problem',
                'safe', 'resource'],
    # Available orders: ['date', 'status', 'name', 'author']
    'orders': ['-date'],

    # Available filters (id [types], (example value)):
    # name [iexact, istartswith, icontains] (<any text>)
    # change_author [is] (<id in the table>)
    # change_date [younger, older] (weeks|days|hours|minutes: <number>)
    # status [is, isnot] (<status identifier>)
    # resource:component [iexact, istartswith, icontains] (<any text>)
    # problem:component [iexact, istartswith, icontains] (<any text>)
    # problem:problem [iexact, istartswith, icontains] (<any text>)
    # format [is] (<number>)
    'filters': {
        # 'name': {
        #     'type': 'istartswith',
        #     'value': 'Title of the job',
        # },
        # 'change_author': {
        #     'type': 'is',
        #     'value': '1',
        # },
        # 'change_date': {
        #     'type': 'younger',
        #     'value': 'weeks:2',
        # },
        # 'resource_component': {
        #     'type': 'istartswith',
        #     'value': 'D',
        # },
        # 'problem_problem': {
        #     'type': 'icontains',
        #     'value': '1',
        # },
        # 'format': {
        #     'type': 'is',
        #     'value': '1',
        # },
    },
}

LANGUAGES = (
    ('en', 'English'),
    ('ru', 'Русский'),
)

USER_ROLES = (
    ('0', _('No access')),
    ('1', _('Producer')),
    ('2', _('Manager')),
    ('3', _('Expert'))
)

VIEW_TYPES = {
    ('1', 'job tree'),
    ('2', 'job view'),
    ('3', 'component children list'),
    ('4', 'unsafes list'),
    ('5', 'safes list'),
    ('6', 'unknowns list'),
    ('7', 'others'),
}

JOB_STATUS = (
    ('0', _('Not solved')),
    ('1', _('Is solving')),
    ('2', _('Stopped')),
    ('3', _('Solved')),
    ('4', _('Failed')),
)

MARK_STATUS = (
    ('0', _('Unreported')),
    ('1', _('Reported')),
    ('2', _('Fixed')),
    ('3', _('Rejected')),
)

MARK_UNSAFE = (
    ('0', _('Unknown')),
    ('1', _('Bug')),
    ('2', _('Target bug')),
    ('3', _('False Positive')),
)

MARK_SAFE = (
    ('0', _('Unknown')),
    ('1', _('Incorrect proof')),
    ('2', _('Missed target bug')),
)

UNSAFE_VERDICTS = (
    ('0', _('Unknown')),
    ('1', _('Bug')),
    ('2', _('Target bug')),
    ('3', _('False positive')),
    ('4', _('Incompatible marks')),
    ('5', _('Without marks')),
)

SAFE_VERDICTS = (
    ('0', _('Unknown')),
    ('1', _('Incorrect proof')),
    ('2', _('Missed target bug')),
    ('3', _('Incompatible marks')),
    ('4', _('Without marks')),
)

VIEWJOB_DEF_VIEW = {
    'data': [
        'unsafes',
        'safes',
        'unknowns',
        'resources',
        'tags_safe',
        'tags_unsafe'
    ],
    # Available filters (id [types], (example value)):
    # unknown_component [iexact, istartswith, icontains] (<any text>)
    # unknown_problem [iexact, istartswith, icontains] (<any text>)
    # resource_component [iexact, istartswith, icontains] (<any text>)
    # safe_tag [iexact, istartswith, icontains] (<any text>)
    # unsafe_tag [iexact, istartswith, icontains] (<any text>)
    # unknowns_total [hide, show]
    # unknowns_nomark [hide, show]
    'filters': {
        # 'unknown_component': {
        #     'type': 'istartswith',
        #     'value': 'D'
        # },
        # 'unknown_problem': {
        #     'type': 'icontains',
        #     'value': 'Problem'
        # },
        # 'resource_component': {
        #     'type': 'icontains',
        #     'value': 'S'
        # },
        # 'safe_tag': {
        #     'type': 'iexact',
        #     'value': 'my:safe:tag:4'
        # },
        # 'unsafe_tag': {
        #     'type': 'istartswith',
        #     'value': 'my:unsafe:'
        # },
        # 'unknowns_total': {
        #     'type': 'hide'
        # },
        # 'unknowns_nomark': {
        #     'type': 'hide'
        # },
        # 'resource_total': {
        #     'type': 'hide'
        # },
    }
}

REPORT_ATTRS_DEF_VIEW = {
    # Available filters (id [types], (example attr), (example value)):
    # component [iexact, istartswith, icontains] (<any text>)
    # attr [iexact, istartswith]
    #     (<attribute name separated by ':'>) (<any text>)
    'filters': {
        # 'component': {
        #     'type': 'istartswith',
        #     'value': 'v',
        # },
        # 'attr': {
        #     'attr': 'Linux kernel verification objs gen strategy:name',
        #     'type': 'istartswith',
        #     'value': 'Separate'
        # }
    }
}

UNSAFE_LIST_DEF_VIEW = {
    'columns': ['mark_verdict', 'mark_result', 'mark_status'],
    # 'order': 'verification obj',
    'filters': {
        # 'attr': {
        #     'attr': 'Linux kernel verification objs gen strategy:name',
        #     'type': 'istartswith',
        #     'value': 'Separate'
        # }
    }
}

SAFE_LIST_DEF_VIEW = {
    'columns': ['mark_verdict', 'mark_status'],
    # 'order': 'verification obj',
    'filters': {
        # 'attr': {
        #     'attr': 'Linux kernel verification objs gen strategy:name',
        #     'type': 'istartswith',
        #     'value': 'Separate'
        # }
    }
}

UNKNOWN_LIST_DEF_VIEW = {
    # 'order': 'verification obj',
    'filters': {
        # 'component': {
        #     'type': 'istartswith',
        #     'value': 'v',
        # },
        # 'attr': {
        #     'attr': 'Linux kernel verification objs gen strategy:name',
        #     'type': 'istartswith',
        #     'value': 'Separate'
        # }
    }
}
