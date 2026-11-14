"""Contrast tests for the YAML 1.1 sexagesimal (base-60) implicit resolvers
and the opt-in ``NoSexagesimalResolver`` loaders.

The default loaders follow the YAML 1.1 schema, where ``1:30`` is an integer
(``90``) and ``190:20:30.15`` is a float (``685230.15``).  The
``*LoaderNoSexagesimal`` loaders follow the YAML 1.2 Core Schema instead:
colon-separated scalars match no implicit resolver and are kept as verbatim
strings, while every other implicit type resolves exactly as before.
"""

import re

import pytest

import yaml
from yaml.resolver import (
    Resolver,
    NoSexagesimalResolver,
    ResolverError,
)
from yaml.loader import (
    SafeLoader,
    FullLoader,
    UnsafeLoader,
    SafeLoaderNoSexagesimal,
    FullLoaderNoSexagesimal,
    UnsafeLoaderNoSexagesimal,
)


INT_TAG = 'tag:yaml.org,2002:int'
FLOAT_TAG = 'tag:yaml.org,2002:float'
STR_TAG = 'tag:yaml.org,2002:str'

SEXAGESIMAL_PATTERN = r'(?::[0-5]?[0-9])+'

NO_SEXAGESIMAL_LOADERS = [
    SafeLoaderNoSexagesimal,
    FullLoaderNoSexagesimal,
    UnsafeLoaderNoSexagesimal,
]
# (loader family, matching no-sexagesimal loader)
LOADER_PAIRS = [
    (SafeLoader, SafeLoaderNoSexagesimal),
    (FullLoader, FullLoaderNoSexagesimal),
    (UnsafeLoader, UnsafeLoaderNoSexagesimal),
]


# ---------------------------------------------------------------------------
# Flat scalars: the two interpretations side by side
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('text, expected', [
    ('1:30', 90),              # 1*60 + 30
    ('8:00', 480),             # 8*60
    ('190:20:30', 685230),     # 190*3600 + 20*60 + 30
    ('+190:20:30', 685230),
    ('-190:20:30', -685230),
    ('12:30:59', 45059),
])
def test_default_loaders_resolve_sexagesimal_ints(text, expected):
    assert yaml.safe_load(text) == expected
    assert isinstance(yaml.safe_load(text), int)
    assert yaml.full_load(text) == expected
    assert yaml.unsafe_load(text) == expected


@pytest.mark.parametrize('text, expected', [
    ('190:20:30.15', 685230.15),
    ('1:00.5', 60.5),
])
def test_default_loaders_resolve_sexagesimal_floats(text, expected):
    assert yaml.safe_load(text) == pytest.approx(expected)
    assert isinstance(yaml.safe_load(text), float)


@pytest.mark.parametrize('loader', NO_SEXAGESIMAL_LOADERS)
@pytest.mark.parametrize('text', [
    '1:30',
    '8:00',
    '190:20:30',
    '+190:20:30',
    '-190:20:30',
    '12:30:59',
    '190:20:30.15',
    '1:00.5',
    # already a string under the default rules, must stay identical
    '01:30',
])
def test_no_sexagesimal_loaders_keep_colon_scalars_as_strings(loader, text):
    result = yaml.load(text, Loader=loader)
    assert result == text
    assert type(result) is str


@pytest.mark.parametrize('loader', NO_SEXAGESIMAL_LOADERS)
def test_no_sexagesimal_node_tag_is_string(loader):
    node = yaml.compose('1:30', Loader=loader)
    assert node.tag == STR_TAG
    assert node.value == '1:30'


def test_default_node_tag_remains_int():
    node = yaml.compose('1:30')
    assert node.tag == INT_TAG
    assert node.value == '1:30'


# ---------------------------------------------------------------------------
# Non-sexagesimal implicit types must be byte-for-byte identical under both
# interpretations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('text, expected', [
    ('42', 42),
    ('-7', -7),
    ('0', 0),
    ('0b101', 5),
    ('0x1A', 26),
    ('0o17', '0o17'),          # YAML 1.1 octal needs a leading 0 without 'o'
    ('017', 15),
    ('3.14', 3.14),
    ('.inf', float('inf')),
    ('.nan', float('nan')),
    ('yes', True),
    ('no', False),
    ('null', None),
    ('plain', 'plain'),
])
def test_other_implicit_types_unchanged(text, expected):
    default_value = yaml.safe_load(text)
    for loader in NO_SEXAGESIMAL_LOADERS:
        switched_value = yaml.load(text, Loader=loader)
        if isinstance(expected, float) and expected != expected:
            assert switched_value != switched_value
        else:
            assert switched_value == default_value == expected
        assert type(switched_value) is type(default_value)


def test_timestamp_resolution_unchanged():
    text = '2020-01-02 03:04:05'
    import datetime
    expected = datetime.datetime(2020, 1, 2, 3, 4, 5)
    assert yaml.safe_load(text) == expected
    for loader in NO_SEXAGESIMAL_LOADERS:
        assert yaml.load(text, Loader=loader) == expected


def test_explicit_tags_override_resolver():
    # explicit !!str always wins
    assert yaml.load('!!str 1:30', Loader=SafeLoader) == '1:30'
    # explicit !!int still constructs through construct_yaml_int even when
    # implicit sexagesimal resolution is disabled
    assert yaml.load('!!int 1:30',
                     Loader=SafeLoaderNoSexagesimal) == 90


# ---------------------------------------------------------------------------
# Nested structures: mapping / sequence / deeply nested combinations, under
# both interpretations
# ---------------------------------------------------------------------------

NESTED_DOCUMENT = """
tasks:
  - name: alpha
    period: 1:30
  - name: beta
    period: 8:00
matrix:
  rows:
    - slot: 12:30:59
      value: 190:20:30.15
plain_int: 685230
plain_float: 3.14
label: unchanged
"""

NESTED_DEFAULT = {
    'tasks': [
        {'name': 'alpha', 'period': 90},
        {'name': 'beta', 'period': 480},
    ],
    'matrix': {
        'rows': [
            {'slot': 45059, 'value': 685230.15},
        ],
    },
    'plain_int': 685230,
    'plain_float': 3.14,
    'label': 'unchanged',
}

NESTED_NO_SEXAGESIMAL = {
    'tasks': [
        {'name': 'alpha', 'period': '1:30'},
        {'name': 'beta', 'period': '8:00'},
    ],
    'matrix': {
        'rows': [
            {'slot': '12:30:59', 'value': '190:20:30.15'},
        ],
    },
    'plain_int': 685230,
    'plain_float': 3.14,
    'label': 'unchanged',
}


def test_nested_document_default_interpretation():
    result = yaml.safe_load(NESTED_DOCUMENT)
    assert result == NESTED_DEFAULT
    # the time fields really became numbers
    assert isinstance(result['tasks'][0]['period'], int)
    assert isinstance(result['matrix']['rows'][0]['value'], float)
    # non-colon fields keep their normal types
    assert isinstance(result['plain_int'], int)


@pytest.mark.parametrize('loader', NO_SEXAGESIMAL_LOADERS)
def test_nested_document_no_sexagesimal_interpretation(loader):
    result = yaml.load(NESTED_DOCUMENT, Loader=loader)
    assert result == NESTED_NO_SEXAGESIMAL
    # verbatim preservation, including characters and sign
    assert result['tasks'][0]['period'] == '1:30'
    assert result['tasks'][1]['period'] == '8:00'
    assert result['matrix']['rows'][0]['slot'] == '12:30:59'
    assert result['matrix']['rows'][0]['value'] == '190:20:30.15'
    assert all(type(v) is str for v in [
        result['tasks'][0]['period'],
        result['tasks'][1]['period'],
        result['matrix']['rows'][0]['slot'],
        result['matrix']['rows'][0]['value'],
    ])
    # non-colon scalars are untouched inside the same nested structure
    assert result['plain_int'] == 685230
    assert type(result['plain_int']) is int
    assert result['plain_float'] == 3.14
    assert type(result['plain_float']) is float
    assert result['label'] == 'unchanged'


def test_nested_sequence_of_mappings_contrast():
    document = "- window: 1:30\n- window: 2:45\n- window: 685230\n"
    assert yaml.safe_load(document) == [
        {'window': 90}, {'window': 165}, {'window': 685230}]
    assert yaml.load(document, Loader=SafeLoaderNoSexagesimal) == [
        {'window': '1:30'}, {'window': '2:45'}, {'window': 685230}]


def test_nested_mapping_with_sequence_values_contrast():
    document = "windows: [1:30, 8:00, 42]\n"
    assert yaml.safe_load(document) == {'windows': [90, 480, 42]}
    assert yaml.load(document, Loader=SafeLoaderNoSexagesimal) == \
        {'windows': ['1:30', '8:00', 42]}


def test_colon_scalar_used_as_mapping_key_contrast():
    document = "1:30: ninety minutes\n"
    assert yaml.safe_load(document) == {90: 'ninety minutes'}
    assert yaml.load(document, Loader=SafeLoaderNoSexagesimal) == \
        {'1:30': 'ninety minutes'}


def test_load_all_multiple_documents_contrast():
    stream = "period: 1:30\n---\nperiod: 8:00\n"
    assert list(yaml.load_all(stream, Loader=SafeLoader)) == [
        {'period': 90}, {'period': 480}]
    assert list(yaml.load_all(stream, Loader=SafeLoaderNoSexagesimal)) == [
        {'period': '1:30'}, {'period': '8:00'}]


# ---------------------------------------------------------------------------
# Resolver table isolation and the replace_implicit_resolver primitive
# ---------------------------------------------------------------------------

def _patterns_for(loader_class, tag):
    return [
        regexp.pattern
        for entries in loader_class.yaml_implicit_resolvers.values()
        for existing_tag, regexp in entries
        if existing_tag == tag
    ]


def test_default_resolver_keeps_sexagesimal_branches():
    int_patterns = _patterns_for(Resolver, INT_TAG)
    float_patterns = _patterns_for(Resolver, FLOAT_TAG)
    assert int_patterns and all(
        SEXAGESIMAL_PATTERN in p for p in int_patterns)
    assert float_patterns and all(
        SEXAGESIMAL_PATTERN in p for p in float_patterns)
    # default loaders share the untouched Resolver table
    for loader_class in (SafeLoader, FullLoader, UnsafeLoader):
        assert loader_class.yaml_implicit_resolvers \
            is Resolver.yaml_implicit_resolvers


def test_no_sexagesimal_resolver_drops_only_sexagesimal_branches():
    int_patterns = _patterns_for(NoSexagesimalResolver, INT_TAG)
    float_patterns = _patterns_for(NoSexagesimalResolver, FLOAT_TAG)
    assert int_patterns and all(
        SEXAGESIMAL_PATTERN not in p for p in int_patterns)
    assert float_patterns and all(
        SEXAGESIMAL_PATTERN not in p for p in float_patterns)
    # table is a copy: mutating it must not touch the default Resolver
    assert NoSexagesimalResolver.yaml_implicit_resolvers \
        is not Resolver.yaml_implicit_resolvers
    for loader_class in NO_SEXAGESIMAL_LOADERS:
        assert loader_class.yaml_implicit_resolvers \
            is NoSexagesimalResolver.yaml_implicit_resolvers


def test_resolver_entry_order_is_preserved():
    def order(table):
        return [
            tag
            for first, entries in table.items()
            if first == '1'
            for tag, _ in entries
        ]
    assert order(NoSexagesimalResolver.yaml_implicit_resolvers) == \
        order(Resolver.yaml_implicit_resolvers)


def test_replace_implicit_resolver_keeps_position():
    class CustomResolver(NoSexagesimalResolver):
        pass

    original = CustomResolver.yaml_implicit_resolvers['1']
    index_before = [tag for tag, _ in original].index(INT_TAG)
    replacement = re.compile(r'^[0-9]+$')
    CustomResolver.replace_implicit_resolver(INT_TAG, replacement)
    entries = CustomResolver.yaml_implicit_resolvers['1']
    index_after = [tag for tag, _ in entries].index(INT_TAG)
    assert index_before == index_after
    assert dict(entries)[INT_TAG] is replacement
    # only the subclass table changed; the default Resolver is untouched
    assert CustomResolver.yaml_implicit_resolvers \
        is not Resolver.yaml_implicit_resolvers
    assert all(
        regexp is not replacement
        for entries in Resolver.yaml_implicit_resolvers.values()
        for tag, regexp in entries)


def test_replace_implicit_resolver_raises_on_unknown_tag():
    class CustomResolver(NoSexagesimalResolver):
        pass

    with pytest.raises(ResolverError):
        CustomResolver.replace_implicit_resolver(
            'tag:yaml.org,2002:not-registered', re.compile(r'.*'))


def test_add_implicit_resolver_still_appends():
    # the existing public API must keep its historical append semantics
    class CustomResolver(Resolver):
        pass

    before = len(CustomResolver.yaml_implicit_resolvers['1'])
    CustomResolver.add_implicit_resolver(
        'tag:example.com,2026:custom', re.compile(r'^custom$'), ['c'])
    assert len(CustomResolver.yaml_implicit_resolvers['c']) == 1
    assert len(CustomResolver.yaml_implicit_resolvers['1']) == before
