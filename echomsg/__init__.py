import os
import sys
import six
import hashlib

from pyparsing import *
from collections import OrderedDict

LANGUAGES = ["cpp", "python"]

default_language = "cpp"

def set_default_language(language):
    if language in LANGUAGES:
        global default_language
        default_language = language

def remove_duplicates(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


class Type(object):

    def __init__(self, name, hash):
        self._name = name
        self._hash = hash

    def get_name(self):
        return self._name

    def get_container(self, language=None):
        return self._name

    def get_default(self, language=None):
        return None

    def get_reader(self, language=None):
        return None

    def get_writer(self, language=None):
        return None

    def get_hash(self):
        return self._hash

class ExternalType(Type):     
    def __init__(self, name, container, default = None, reader = {}, writer = {}):
        super(ExternalType, self).__init__(name, name)
        self._default = default
        self._container = container
        self._reader = reader
        self._writer = writer

    def get_container(self, language=None):
        language = language if language else default_language
        if isinstance(self._container, dict):
            return self._container.get(language, None)
        return self._container

    def get_default(self, language=None):
        language = language if language else default_language
        if isinstance(self._default, dict):
            return self._default.get(language, None)
        return self._default

    def get_reader(self, language=None):
        language = language if language else default_language
        if isinstance(self._reader, dict):
            return self._reader.get(language, None)
        return self._reader

    def get_writer(self, language=None):
        language = language if language else default_language
        if isinstance(self._writer, dict):
            return self._writer.get(language, None)
        return self._writer

class Source(object):

    def __init__(self, code):
        self.code = code

    def __str__(self):
        return self.code

def make_keyword(kwd_str, kwd_value):
    return Keyword(kwd_str).setParseAction(replaceWith(kwd_value))

def formatConstant(value, language="cpp"):
    if isinstance(value, Source):
        return str(value)
    if value is None and language == "cpp":
        return ""
    if value is None and language == "python":
        return "None"
    elif isinstance(value, bool):
        if language == "cpp":
            return "true" if value else "false"
        if language == "python":
            return "True" if value else "False"
    if isinstance(value, six.integer_types):
        return str(value)
    if isinstance(value, float):
        return "%.f" % (value)
    elif isinstance(value, six.string_types):
        return "\"%s\"" % value
    return str(value)

class DescriptionError(Exception):
    
    def __init__(self, file, line, column, message):
        super(Exception, self).__init__()
        self.file = file
        self.line = line
        self.column = column
        self.message = message

    def __str__(self):
        return "{} (line: {}, col: {}): {}".format(self.file, self.line, self.column, self.message)

class MessagesRegistry(object):

    def __init__(self):
        self.enums = OrderedDict()
        self.types = OrderedDict()
        self.add_type(ExternalType("short", {"python" : "int", "cpp": "int16_t"}, 0))
        self.add_type(ExternalType("int", {"python" : "int", "cpp": "int32_t"}, 0))
        self.add_type(ExternalType("long", {"python" : "long", "cpp": "int64_t"}, 0))
        self.add_type(ExternalType("float", {"python" : "float", "cpp": "float"}, 0.0))
        self.add_type(ExternalType("double", {"python" : "echolib.double", "cpp": "double"}, 0.0))
        self.add_type(ExternalType("bool", {"python" : "bool", "cpp": "bool"}, False))
        self.add_type(ExternalType("char", {"python" : "echolib.char", "cpp": "char"}, '\0'))
        self.add_type(ExternalType("string", {"python" : "str", "cpp": "std::string"}, ""))


        self.add_type(ExternalType("Timestamp", {"python" : "datetime.datetime",
            "cpp": "std::chrono::system_clock::time_point"}))

        self.add_type(ExternalType("Header", {"python" : "echolib.Header", "cpp": "echolib::Header"},
            {"python" : Source("echolib.Header()"), "cpp": Source("echolib::Header()")}))

        self.structs = OrderedDict()
        self.messages = []
        self.namespace = None
        self.files = []
        self.sources = {l : [] for l in LANGUAGES}
        self.sources["cpp"].append("vector")
        self.sources["cpp"].append("chrono")
        self.sources["cpp"].append("echolib/datatypes.h")
        self.sources["python"].append("echolib")
        self.sources["python"].append("datetime")
        
    def get_sources(self, language = None):
        language = language if language else default_language
        return self.sources[language]

    def add_enum(self, name, values):
        
        typehash = hashlib.md5()
        for v in values:
            typehash.update(v)
        self.add_type(Type(name, typehash.hexdigest()))
        self.enums[name] = values

    def add_struct(self, name, fields):
        typehash = hashlib.md5()
        for k, v in fields.items():
            t = v['type']
            if not t in self.types:
                raise RuntimeError('Unknown type: ' + t)
            typehash.update(self.types[t].get_hash())                

        self.add_type(Type(name, typehash.hexdigest()))
        self.structs[name] = fields

    def add_message(self, name, fields):
        self.add_struct(name, fields)
        self.messages.append(name)

    def add_type(self, type):
        if type.get_name() in self.types:
            raise RuntimeError('Name already taken: ' + type.get_name())
        self.types[type.get_name()] = type

def processValue(value):
    if "numeric" in value:
        try:
            return int(value["numeric"])
        except ValueError:
            return float(value["numeric"])
    elif "bool" in value:
        return bool(value["bool"])
    else:
        return str(value["string"])

def processFields(fields):
    result = OrderedDict()
    for field in fields:
        name = field["name"]
        result[name] = {"type": field["type"], "default" : None}
        result[name]["array"] = "array" in field
        if result[name]["array"]:
            result[name]["array"] = True
            if "length" in field["array"]:
                result[name]["length"] = int(field["array"]["length"])
#        if "properties" in field:
#           result[name]["properties"]
        if "default" in field:
           result[name]["default"] = processValue(field["default"])
    return result


def parseFile(msgfile, registry, searchpath=[], include=True):

    TRUE = make_keyword("true", True)
    FALSE = make_keyword("false", False)
    NULL = make_keyword("null", None)

    LBRACK, RBRACK, LBRACE, RBRACE, COLON, SEMICOLON, EQUALS, POINT, LANGLE, RANGLE = map(
        Suppress, "[]{}:;=.()")

    Exponent = CaselessLiteral('E')

    MessageFile = dblQuotedString().setParseAction(removeQuotes)
    StringLiteral = dblQuotedString().setParseAction(removeQuotes)

    PlusMinus = Literal('+') | Literal('-')
    Number = Word(nums)
    IntegerValue = Combine( Optional(PlusMinus) + Number )
    FloatValue = Combine( IntegerValue +
                       Optional( POINT + Optional(Number) ) +
                       Optional( Exponent + IntegerValue )
                     )
    BooleanValue = Or( [TRUE | FALSE])

    LanguageName = Word(alphanums)
    FieldName = Word(alphanums + "_")
    FieldType = Word(alphanums)
    PropertyName = Word(alphanums + "_")
    EnumerateConst = Word(nums)
    EnumerateValue = Group(Word(alphanums + "_").setResultsName("name"))
    EnumerateName = Word(alphanums + "_")
    StructureName = Word(alphanums + "_")
    ArrayLength = Word(nums)

    Value = Group(Or([FloatValue.setResultsName("numeric") | StringLiteral.setResultsName("string") | BooleanValue.setResultsName("bool")]))
    Property = Group(PropertyName.setResultsName("name") + EQUALS + Value.setResultsName("value"))
    PropertyList = Group(LANGLE + ZeroOrMore(Property) + RANGLE)

    ExternalLanguage = Group(Literal("language") + LanguageName.setResultsName("language") 
            + StringLiteral.setResultsName("container") 
            + Optional(Literal("from") + OneOrMore(StringLiteral).setResultsName("sources"))
            + Optional(Literal("default") + StringLiteral.setResultsName("default"))
            + Optional(Literal("read") + StringLiteral.setResultsName("read") 
                + Literal("write") + StringLiteral.setResultsName("write"))
            ) + SEMICOLON

    ExternalLanguageList = Group(LANGLE + ZeroOrMore(ExternalLanguage) + RANGLE)


    Field = Group(FieldType.setResultsName("type") + Optional(Group(LBRACK +
        Optional(ArrayLength).setResultsName("length") + RBRACK).setResultsName("array")) +
        FieldName.setResultsName("name") + Optional(EQUALS + Value.setResultsName("default")) + Optional(PropertyList.setResultsName("properties")) + SEMICOLON)
    FieldList = Group(
        LBRACE + ZeroOrMore(Field) + RBRACE).setResultsName('fields')

    Enumerate = Group(Literal("enumerate") + EnumerateName.setResultsName("name") + LBRACE +
                      Group(delimitedList(EnumerateValue)).setResultsName('values') + RBRACE)

    Include = Group(
        Literal("include") + MessageFile.setResultsName('name') + Optional(PropertyList.setResultsName("properties")))  + SEMICOLON

    Import = Group(
        Literal("import") + MessageFile.setResultsName('name')) + SEMICOLON

    External = Group(
        Literal("external") + StructureName.setResultsName('name') + ExternalLanguageList.setResultsName("languages")) + SEMICOLON

    Structure = Group(
        Literal("structure") + StructureName.setResultsName('name') + FieldList)
    Message = Group(
        Literal("message") + StructureName.setResultsName('name') + FieldList)

    Namespace = Group(
        Literal("namespace") + Word(alphanums + ".").setResultsName('name') + SEMICOLON)
    Messages = Optional(
        Namespace) + ZeroOrMore(Or([Enumerate | Include | Import | External | Structure | Message]))
    Messages.ignore(pythonStyleComment)

    if os.path.isabs(msgfile):
        if not os.path.exists(msgfile) or not os.path.isfile(msgfile):
            raise IOError("File '%s' does not exist", msgfile)
    else:
        base = msgfile
        msgfile = None
        for p in searchpath:
            candidate = os.path.join(p, base)
            if os.path.exists(candidate) and os.path.isfile(candidate):
                msgfile = candidate
                break

    if msgfile in registry.files:
        print "%s already processed, ignoring." % msgfile
        return

    registry.files.append(msgfile)

    if not msgfile:
        raise IOError("File '%s' does not exist in search path" % base)

    try:
        parse = Messages.parseFile(msgfile, True)
    except ParseException, e:
        raise DescriptionError(msgfile, e.lineno, e.col, e.msg)

    try:

        for e in parse:
            name = e[0]
            if name == 'namespace':
                registry.namespace = e["name"]
            if name == 'import':
                parseFile(e["name"], registry, searchpath, False)
            if name == 'include':
                properties = {a["name"] : a["value"] for a in e.get("properties", [])}
                parseFile(e["name"], registry, searchpath, True)
            if name == 'external':
                containers = {l: e["name"] for l in LANGUAGES}
                defaults = {}
                readers = {}
                writers = {}
                declared = []
                for l in e.get("languages", []):
                    if not l["language"] in LANGUAGES:
                        raise RuntimeError("Unknown language {}".format(l["language"]))
                    if l["language"] in declared:
                        raise RuntimeError("Duplicate declaration {}".format(l["language"]))
                    declared.append(l["language"])
                    containers[l["language"]] = l["container"] # Override container name
                    if l.get("default", None):
                        defaults[l["language"]] = Source(l["default"])
                    if l.get("sources", None):
                        registry.sources[l["language"]].extend(l["sources"])
                    if l.get("read", None):
                        readers[l["language"]] = Source(l["read"])
                        writers[l["language"]] = Source(l["write"])

                registry.add_type(ExternalType(e["name"], containers, defaults, readers, writers))
            if name == 'enumerate':
                values = {v["name"]: k for v, k in zip(e["values"], range(len(e["values"])))}
                registry.add_enum(e["name"], values)
            if name == 'structure':
                fields = processFields(e["fields"])
                registry.add_struct(e["name"], fields)
            if name == 'message':
                fields = processFields(e["fields"])
                registry.add_message(e["name"], fields)

        registry.sources = {k: remove_duplicates(l) for k, l in registry.sources.items()}


    except RuntimeError, ex:
        print(type(e))
        raise DescriptionError(msgfile, 0, 0, str(ex))


