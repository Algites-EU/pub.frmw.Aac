#!/usr/bin/env python3
"""Derive canonical YAML/XML schema views and config examples from AAC jsondefs.

Yamldefs retain the canonical JSON Schema semantics exactly. XSD 1.0 is a typed XML
projection and embeds the full authoritative JSON schema for non-representable rules.
New canonical definitions deliberately do not receive publication metadata sidecars.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import yaml
from lxml import etree

XS = 'http://www.w3.org/2001/XMLSchema'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'
AAC = 'urn:algites:aac:xml-schema-compatibility:1'
NS = {'xs': XS, 'aac': AAC}
SITE = 'https://defs.dev.algites.eu/api'
JSON_SUFFIX = '.jsondef.schema.json'
YAML_SUFFIX = '.yamldef.schema.json'


def elt(parent, tag, **attrs):
    return etree.SubElement(parent, '{%s}%s' % (XS, tag), **{k: str(v) for k,v in attrs.items()})


def pascal(stem):
    return ''.join(word[:1].upper() + word[1:] for word in re.split(r'[^a-zA-Z0-9]+', re.sub(r'_\d+$', '', stem)) if word)


def change_refs(value, suffix):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == '$ref' and isinstance(item, str):
                value[key] = item.replace('/jsondefs/', '/yamldefs/').replace(JSON_SUFFIX, suffix)
            elif key == '$id' and isinstance(item, str):
                value[key] = item.replace('/src/product/jsondefs/', '/src/product/yamldefs/').replace('/api/jsondefs/', '/api/yamldefs/').replace(JSON_SUFFIX, suffix)
            else:
                change_refs(item, suffix)
    elif isinstance(value, list):
        for item in value:
            change_refs(item, suffix)


def annotation(element, schema, original=None):
    description = schema.get('description') or schema.get('title')
    if not description and original is None:
        return
    note = elt(element, 'annotation')
    if description:
        elt(note, 'documentation').text = description
    if original is not None:
        appinfo = elt(note, 'appinfo')
        etree.SubElement(appinfo, '{%s}canonicalJsonSchema' % AAC, sourceFormat='jsondefs').text = json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        etree.SubElement(appinfo, '{%s}validationNote' % AAC).text = (
            'XSD 1.0 structural projection. For oneOf/anyOf/allOf, if/then/else, '
            'uniqueItems, JSON patterns, open-key maps and cross-field rules, '
            'the embedded canonical JSON schema remains authoritative.'
        )


def resolve(schema, document, source, visited=None):
    """Resolve direct JSON Schema references; preserve broader composition for annotations."""
    visited = set() if visited is None else visited
    if not isinstance(schema, dict):
        return {}
    if '$ref' not in schema:
        return schema
    ref = schema['$ref']
    if ref in visited:
        return {'description': 'Recursive reference ' + ref}
    if ref.startswith('#/'):
        node = document
        for part in ref[2:].split('/'):
            node = node[part.replace('~1', '/').replace('~0', '~')]
        return resolve(node, document, source, visited | {ref})
    if '#' in ref:
        location, fragment = ref.split('#',1)
    else:
        location, fragment = ref, ''
    target = (source.parent / location).resolve()
    if not target.is_file():
        return {'description': 'External schema reference ' + ref}
    target_document = json.loads(target.read_text(encoding='utf-8'))
    other = target_document
    if fragment.startswith('/'):
        for part in fragment[1:].split('/'):
            other = other[part.replace('~1','/').replace('~0','~')]
    return resolve(other, target_document, target, visited | {ref})


def kind(schema):
    typ = schema.get('type')
    if isinstance(typ, list):
        typ = next((v for v in typ if v != 'null'), None) if len([v for v in typ if v != 'null']) == 1 else None
    return typ or ('object' if 'properties' in schema else 'array' if 'items' in schema else None)


def scalar_type(schema):
    typ = kind(schema)
    if typ == 'integer':
        return 'xs:integer'
    if typ == 'number':
        return 'xs:decimal'
    if typ == 'boolean':
        return 'xs:boolean'
    # JSON Schema formats are annotations (validation may not assert lexical range).
    return 'xs:string'


def constrain_simple(node, schema):
    base = scalar_type(schema)
    values = schema.get('enum', [schema['const']] if 'const' in schema else None)
    facets = []
    if isinstance(values, list) and all(isinstance(x,(str,int,float,bool)) and x is not None for x in values):
        facets += [('enumeration', 'true' if x is True else 'false' if x is False else str(x)) for x in values]
    for source, dest in [('minLength','minLength'), ('maxLength','maxLength'), ('minimum','minInclusive'), ('maximum','maxInclusive'), ('exclusiveMinimum','minExclusive'), ('exclusiveMaximum','maxExclusive')]:
        if source in schema and isinstance(schema[source],(int,float)) and not isinstance(schema[source],bool):
            facets.append((dest, schema[source]))
    if not facets:
        node.set('type', base)
        return
    simple = elt(node, 'simpleType')
    restriction = elt(simple, 'restriction', base=base)
    for name, value in facets:
        elt(restriction, name, value=value)


def build_element(parent, name, raw, document, source, required=False, depth=0):
    node = elt(parent, 'element', name=name)
    if not required:
        node.set('minOccurs','0')
    schema = resolve(raw, document, source)
    if not schema:
        node.set('type', 'xs:anyType')
        return node
    if isinstance(raw.get('type'), list) and 'null' in raw['type']:
        node.set('nillable', 'true')
    annotation(node, raw)
    typ = kind(schema)
    if depth > 24:
        node.set('type','xs:anyType')
    elif typ == 'object':
        make_object(node, schema, document, source, depth + 1)
    elif typ == 'array':
        complex_type = elt(node,'complexType')
        seq = elt(complex_type,'sequence')
        item = build_element(seq,'Item', schema.get('items',{}), document, source, False, depth+1)
        item.set('minOccurs',str(schema.get('minItems',0)))
        item.set('maxOccurs',str(schema.get('maxItems','unbounded')))
    elif typ in ('integer','number','boolean','string'):
        constrain_simple(node,schema)
    else:
        node.set('type','xs:anyType')
    return node


def make_object(node, schema, document, source, depth):
    complex_type = elt(node,'complexType')
    sequence = elt(complex_type,'sequence')
    properties = schema.get('properties',{})
    required = set(schema.get('required',[]))
    for name, child in properties.items():
        if name == '$schema':
            continue
        if re.fullmatch('[a-zA-Z_][a-zA-Z0-9_.-]*',name):
            build_element(sequence,name,child,document,source,name in required,depth+1)
    # Open maps with known fields require a representation that does not violate XSD 1.0 UPA.
    # Reserved MapEntry elements preserve unknown keys without conflicting with declared names.
    additional = schema.get('additionalProperties', True)
    if additional is not False:
        extra = elt(sequence,'element',name='MapEntry',minOccurs='0',maxOccurs='unbounded')
        typ=elt(extra,'complexType')
        content=elt(typ,'sequence')
        elt(content,'any',minOccurs='0',maxOccurs='unbounded',processContents='lax')
        elt(typ,'attribute',name='key',type='xs:string',use='required')
    if '$schema' in properties:
        attr = elt(complex_type,'attribute',name='schemaRef',type='xs:anyURI',use='required' if '$schema' in required else 'optional')
        annotation(attr,{'description':'XML representation of the JSON $schema property.'})


def create_xsd(src, dest, canonical):
    relative = src.as_posix().split('/src/product/jsondefs/',1)[1].replace(JSON_SUFFIX,'.xsd')
    namespace = SITE+'/xmldefs/'+relative
    root = etree.Element('{%s}schema' % XS, nsmap={'xs':XS,'aac':AAC,'tns':namespace},
                         targetNamespace=namespace, elementFormDefault='qualified')
    annotation(root,canonical,canonical)
    name = pascal(src.name.removesuffix(JSON_SUFFIX))
    top = elt(root,'element',name=name)
    annotation(top,canonical)
    if kind(canonical)=='object':
        make_object(top,canonical,canonical,src,0)
    else:
        constrain_simple(top,canonical)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True))
    return namespace, name


def serialize_xml(parent, key, value, schema, document, source):
    child = etree.SubElement(parent,'{%s}%s' % (etree.QName(parent).namespace,key))
    schema = resolve(schema, document, source)
    if value is None:
        child.set('{%s}nil' % XSI,'true')
    elif isinstance(value,dict):
        props=schema.get('properties',{})
        for name, sub_schema in props.items():
            if name in value and name != '$schema':
                serialize_xml(child,name,value[name],sub_schema,document,source)
        for name, v in value.items():
            if name == '$schema':
                child.set('schemaRef',str(v).replace('/api/jsondefs/','/api/xmldefs/').replace(JSON_SUFFIX,'.xsd'))
            elif name not in props:
                entry=etree.SubElement(child,'{%s}MapEntry'%etree.QName(parent).namespace,key=name)
                # Non-schema dynamic keys cannot be strongly typed by an XSD 1.0 wildcard.
                etree.SubElement(entry,'{%s}Value' % etree.QName(parent).namespace).text=json.dumps(v,ensure_ascii=False)
    elif isinstance(value,list):
        item_schema=schema.get('items',{})
        for item in value:
            serialize_xml(child,'Item',item,item_schema,document,source)
    elif isinstance(value,bool):
        child.text='true' if value else 'false'
    else:
        child.text=str(value)
    return child


def create_xml_config(path, yaml_data, schema_src, xsd_namespace, root_name):
    schema=json.loads(schema_src.read_text(encoding='utf-8'))
    xml=etree.Element('{%s}%s'%(xsd_namespace,root_name), nsmap={None:xsd_namespace,'xsi':XSI})
    xml.set('{%s}schemaLocation'%XSI,xsd_namespace+' '+xsd_namespace)
    schema_fields=schema.get('properties',{})
    if '$schema' in yaml_data:
        xml.set('schemaRef',yaml_data['$schema'].replace('/api/jsondefs/','/api/xmldefs/').replace(JSON_SUFFIX,'.xsd'))
    for key, child_schema in schema_fields.items():
        if key in yaml_data and key != '$schema':
            serialize_xml(xml,key,yaml_data[key],child_schema,schema,schema_src)
    missing=set(yaml_data)-set(schema_fields)
    if missing:
        raise ValueError(f'{path}: YAML contains fields missing from schema: {missing}')
    path.with_suffix('.xml').write_bytes(etree.tostring(xml,encoding='UTF-8',xml_declaration=True,pretty_print=True))


def generate(root):
    schemas={}
    for source in sorted(root.glob('**/src/product/jsondefs/**/*'+JSON_SUFFIX)):
        document=json.loads(source.read_text(encoding='utf-8'))
        yml_source=Path(str(source).replace('/src/product/jsondefs/','/src/product/yamldefs/').replace(JSON_SUFFIX,YAML_SUFFIX))
        xml_source=Path(str(source).replace('/src/product/jsondefs/','/src/product/xmldefs/').replace(JSON_SUFFIX,'.xsd'))
        yaml_copy=copy.deepcopy(document)
        change_refs(yaml_copy,YAML_SUFFIX)
        # The self-contained schema remains JSON Schema even for YAML payload validation.
        yml_source.parent.mkdir(parents=True,exist_ok=True)
        yml_source.write_text(json.dumps(yaml_copy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        ns, root_name = create_xsd(source,xml_source,document)
        schema_rel=source.as_posix().split('/src/product/jsondefs/',1)[1]
        schemas[schema_rel]=(source,ns,root_name)
    config_count=0
    for cfg in sorted(root.glob('**/src/product/config/**/*.yml')):
        if cfg.name.endswith('.meta.yml') or cfg.name.endswith('.meta.yaml'):
            continue
        text=cfg.read_text(encoding='utf-8')
        data=yaml.safe_load(text)
        schema_url=data.get('$schema','')
        if '/api/jsondefs/' in schema_url:
            json_url=schema_url
            yaml_url=schema_url.replace('/api/jsondefs/','/api/yamldefs/').replace(JSON_SUFFIX,YAML_SUFFIX)
        elif '/api/yamldefs/' in schema_url:
            yaml_url=schema_url
            json_url=schema_url.replace('/api/yamldefs/','/api/jsondefs/').replace(YAML_SUFFIX,JSON_SUFFIX)
        else:
            raise ValueError(f'Unexpected canonical schema header in {cfg}: {schema_url}')
        schema_rel=json_url.split('/api/jsondefs/',1)[1]
        if schema_rel not in schemas:
            raise ValueError(f'Missing canonical schema {schema_rel} for {cfg}')
        source, ns, root_name = schemas[schema_rel]
        # Preserve YAML formatting and data contents outside URL references.
        updated_text=text.replace(json_url,yaml_url)
        # A configuration schema Resource must point to the same technology's definition.
        updated_text=re.sub(r'(?m)^(\s*Resource:\s*\S+?)\.jsondef\.schema\.json(\s*)$',
                            r'\1.yamldef.schema.json\2',updated_text)
        cfg.write_text(updated_text,encoding='utf-8')
        yaml_data=yaml.safe_load(updated_text)

        def format_resource_values(value, extension):
            if isinstance(value,dict):
                for key,child in value.items():
                    if key=='Resource' and isinstance(child,str):
                        value[key]=re.sub(r'(?:\.jsondef\.schema\.json|\.yamldef\.schema\.json|\.xsd)$',extension,child)
                    else:
                        format_resource_values(child,extension)
            elif isinstance(value,list):
                for child in value:
                    format_resource_values(child,extension)

        json_data=copy.deepcopy(yaml_data)
        json_data['$schema']=json_url
        format_resource_values(json_data,JSON_SUFFIX)
        cfg.with_suffix('.json').write_text(json.dumps(json_data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

        xml_data=copy.deepcopy(yaml_data)
        format_resource_values(xml_data,'.xsd')
        # XML form maps $schema to schemaRef and xsi:schemaLocation.
        xml_data['$schema']=json_url
        create_xml_config(cfg,xml_data,source,ns,root_name)
        config_count+=1
    return len(schemas),config_count


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('repository',type=Path,nargs='?',default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    print('Generated schema and configuration parity:',generate(args.repository.resolve()))
