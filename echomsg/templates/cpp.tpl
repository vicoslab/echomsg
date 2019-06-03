// This is an autogenerated file, do not modify!

#ifndef __{{ basename|upper }}_MSGS_H
#define __{{ basename|upper }}_MSGS_H

{% for include in registry.get_sources() %}
#include <{{ include }}>
{% endfor %}

namespace echolib {

{% for name, type in registry.types.items() %}
{%- if type.get_reader() and type.get_writer() %}

template <> inline void read(MessageReader& reader, {{ type.get_container() }}& dst) {
	dst = {{ type.get_reader() }}(reader);
}

template <> inline void write(MessageWriter& writer, const {{ type.get_container() }}& src) {
	{{ type.get_writer() }}(writer, src);
}
{% endif -%}
{% endfor %}

}

{% if namespace %}
{% set cppnamespace = namespace.replace('.', '::') + '::' %}
{% for n in namespace.split('.') -%}
namespace {{ n }} {
{% endfor %}
{% endif %}

{% for name, values in registry.enums.items() %}
enum {{ name }} { {% for v in values.keys() %}{{ name|upper }}_{{v}}{% if not loop.last %}, {% endif %}{% endfor %} };
{% endfor %}

{% for name in registry.structs.keys() -%}
class {{ name }};
{% endfor %}

{% for name, fields in registry.structs.items() %}
class {{ name }} {
public:
	{{ name }}(
        {%- for k, v in fields.items() -%}
        {%- set defval = v["default"] if not v["default"] is none else registry.types[v["type"]].get_default() -%}
	    {%- if not loop.first %}, {% endif -%}{%- if not defval is none and not v["array"] -%}
	        {{ registry.types[v["type"]].get_container() }} {{ k }} = {{ defval|constant }}
	    {%- elif v['array'] -%}
            {%- if v['length'] is none -%}
            {{ registry.types[v["type"]].get_container() }} {{ k }}[{{ v['length'] }}] = {}
            {%- else -%}
			std::vector<{{ v["type"] }}> {{ k }} = std::vector<{{ v["type"] }}>()
            {%- endif -%}
        {%- else -%}
        {{ registry.types[v["type"]].get_container() }} {{ k }} = {{ v["type"] }}()
	    {%- endif -%}
	    {%- endfor -%}
	) {

        {% for k, v in fields.items() -%}
        this->{{ k }} = {{ k }};
	    {% endfor -%}

    };
    
	virtual ~{{ name }}() {};
	{% for k, v in fields.items() -%}
	{% if v['array'] and v['length'] is none -%}
	{{ registry.types[v["type"]].get_container() }} {{ k }}[{{ v['length'] }}];
	{% elif v['array'] and not v['length'] is none -%}
	std::vector<{{ registry.types[v["type"]].get_container() }}> {{ k }};
	{% else -%}
	{{ registry.types[v["type"]].get_container() }} {{ k }};
	{% endif -%}
	{%- endfor %}

};
{% endfor %}

{% if namespace %}
{% for n in namespace.split('.') -%}
}
{% endfor %}
{% endif %}

namespace echolib {

{% for name, values in registry.enums.items() %}

template <> inline void read(MessageReader& reader, {{ cppnamespace }}{{ name }}& dst) {
	switch (reader.read<int>()) {
	{% for k, v in values.items() -%}
		case {{ v }}: dst = {{ cppnamespace }}{{ name|upper }}_{{ k }}; break;
	{% endfor %}
	}
}

template <> inline void write(MessageWriter& writer, const {{ cppnamespace }}{{ name }}& src) {
	switch (src) {
	{% for k, v in values.items() -%}
		case {{ cppnamespace }}{{ name|upper }}_{{ k }}: writer.write<int>({{ v }}); return;
	{% endfor %}
	}
}

{% endfor %}


{% for name, fields in registry.structs.items() %}
template <> inline void read(MessageReader& reader, {{ cppnamespace }}{{ name }}& dst) {
	{% for k, v in fields.items() -%}
	read(reader, dst.{{ k }});
	{%- endfor %}
}

template <> inline void write(MessageWriter& writer, const {{ cppnamespace }}{{ name }}& src) {
	{% for k, v in fields.items() -%}
	write(writer, src.{{ k }});
	{%- endfor %}
}
{% endfor %}

{% for name in registry.messages %}
{% set metadata = registry.types[name] %}

template <> inline string get_type_identifier<{{ cppnamespace }}{{ name }}>() { return string("{{ metadata.get_hash() }}"); }

template<> inline shared_ptr<Message> echolib::Message::pack<{{ cppnamespace }}{{ name }} >(const {{ cppnamespace }}{{ name }} &data) {
    MessageWriter writer;
    write(writer, data);
    return make_shared<BufferedMessage>(writer);
}

template<> inline shared_ptr<{{ cppnamespace }}{{ name }} > echolib::Message::unpack<{{ cppnamespace }}{{ name }}>(SharedMessage message) {
    MessageReader reader(message);
    shared_ptr<{{ cppnamespace }}{{ name }}> result(new {{ cppnamespace }}{{ name }}());
    read(reader, *result);
    return result;
}

{% endfor %}

}

#endif
