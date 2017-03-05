import os
import sys
import hashlib

from pyparsing import *
from collections import OrderedDict

def make_keyword(kwd_str, kwd_value):
    return Keyword(kwd_str).setParseAction(replaceWith(kwd_value))

class SemanticError(Exception):
    pass

class MessagesRegistry(object):

    def __init__(self):
        self.enums = OrderedDict()
        self.types = OrderedDict()
        self.types['int'] = {"primitive" : True, "python" : "int", "cpp": "int"}
        self.types['long'] = {"primitive" : True, "python" : "long", "cpp": "long"}
        self.types['float'] = {"primitive" : True, "python" : "float", "cpp": "float"}
        self.types['double'] = {"primitive" : True, "python" : "echolib.double", "cpp": "echolib.double"}
        self.types['bool'] = {"primitive" : True, "python" : "bool", "cpp": "bool"}
        self.types['char'] = {"primitive" : True, "python" : "echolib.char", "cpp": "char"}
        self.types['string'] = {"primitive" : True, "python" : "str", "cpp": "string"}
        self.structs = OrderedDict()
        self.messages = []
        self.namespace = None

    def add_enum(self, name, values):
        self.add_type(name)
        typehash = hashlib.md5()
        for v in values:
            typehash.update(v)
        self.types[name]['typehash'] = typehash.hexdigest()
        self.enums[name] = values

    def add_struct(self, name, fields):
        typehash = hashlib.md5()
        for k, v in fields.items():
            t = v['type']
            if not t in self.types:
                raise SemanticError('Unknown type: ' + t)
            if self.types[t]['primitive'] or self.types[t]['external']:
                typehash.update(t)
            else:
                typehash.update(self.types[t]['typehash'])
        self.add_type(name)
        self.structs[name] = fields
        self.types[name]["typehash"] = typehash.hexdigest()

    def add_message(self, name, fields):
        self.add_struct(name, fields)
        self.messages.append(name)

    def add_type(self, name, external=False):
        if name in self.types:
            raise SemanticError('Name already taken: ' + name)
        self.types[name] = {"primitive" : False, "external" : external, "python" : name, "cpp" : name}

def processValue(value):
    if "numeric" in value:
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


def parseFile(msgfile, registry, searchpath=[]):

    TRUE = make_keyword("true", True)
    FALSE = make_keyword("false", False)
    NULL = make_keyword("null", None)

    LBRACK, RBRACK, LBRACE, RBRACE, COLON, SEMICOLON, EQUALS, POINT, LANGLE, RANGLE = map(
        Suppress, "[]{}:;=.()")

    Exponent = CaselessLiteral('E')

    ImportFile = dblQuotedString().setParseAction(removeQuotes)
    StringLiteral = dblQuotedString().setParseAction(removeQuotes)

    PlusMinus = Literal('+') | Literal('-')
    Number = Word(nums)
    IntegerValue = Combine( Optional(PlusMinus) + Number )
    FloatValue = Combine( IntegerValue +
                       Optional( POINT + Optional(Number) ) +
                       Optional( Exponent + IntegerValue )
                     )
    BooleanValue = Or( [TRUE | FALSE])

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

    Field = Group(FieldType.setResultsName("type") + Optional(Group(LBRACK +
        Optional(ArrayLength).setResultsName("length") + RBRACK).setResultsName("array")) +
        FieldName.setResultsName("name") + Optional(EQUALS + Value.setResultsName("default")) + Optional(PropertyList.setResultsName("properties")) + SEMICOLON)
    FieldList = Group(
        LBRACE + ZeroOrMore(Field) + RBRACE).setResultsName('fields')

    Enumerate = Group(Literal("enumerate") + EnumerateName.setResultsName("name") + LBRACE +
                      Group(delimitedList(EnumerateValue)).setResultsName('values') + RBRACE)
    Import = Group(
        Literal("import") + ImportFile.setResultsName('name')) + SEMICOLON
    External = Group(
        Literal("external") + FieldType.setResultsName('name') + Optional(PropertyList)) + SEMICOLON

    Structure = Group(
        Literal("structure") + StructureName.setResultsName('name') + FieldList)
    Message = Group(
        Literal("message") + StructureName.setResultsName('name') + FieldList)

    Namespace = Group(
        Literal("namespace") + Word(alphanums + ".").setResultsName('name') + SEMICOLON)
    Messages = Optional(
        Namespace) + ZeroOrMore(Or([Enumerate | Import | External | Structure | Message]))
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

    if not msgfile:
        raise IOError("File '%s' does not exist in search path" % base)

    parse = Messages.parseFile(msgfile, True)

    for e in parse:
        name = e[0]
        if name == 'namespace':
            registry.namespace = e["name"]
        if name == 'import':
            parseFile(e["name"], registry, searchpath)
        if name == 'external':
            registry.add_type(e["name"], True)
        if name == 'enumerate':
            values = {v["name"]: k for v, k in zip(e["values"], range(len(e["values"])))}
            registry.add_enum(e["name"], values)
        if name == 'structure':
            fields = processFields(e["fields"])
            registry.add_struct(e["name"], fields)
        if name == 'message':
            fields = processFields(e["fields"])
            registry.add_message(e["name"], fields)


