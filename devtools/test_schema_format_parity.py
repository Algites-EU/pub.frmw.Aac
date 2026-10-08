#!/usr/bin/env python3
"""Regression tests for the three canonical AAC definition and config formats."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from generate_schema_format_parity import JSON_SUFFIX, YAML_SUFFIX, change_refs, kind, resolve, XS, AAC, XSI


def normalize_resources(value, extension):
    if isinstance(value,dict):
        result={}
        for key,child in value.items():
            if key=='Resource' and isinstance(child,str) and child.endswith((JSON_SUFFIX,YAML_SUFFIX,'.xsd')):
                result[key]=child.replace(JSON_SUFFIX,extension).replace(YAML_SUFFIX,extension).replace('.xsd',extension)
            else:
                result[key]=normalize_resources(child,extension)
        return result
    if isinstance(value,list):
        return [normalize_resources(x,extension) for x in value]
    return value


def value_from_xml(elem, schema, document, path):
    schema=resolve(schema,document,path)
    if elem.get('{%s}nil'%XSI)=='true':
        return None
    typ=kind(schema)
    if typ == 'array':
        return [value_from_xml(x,schema.get('items',{}),document,path) for x in elem if etree.QName(x).localname=='Item']
    if typ=='object' or len(elem):
        obj={}
        for c in elem:
            key=etree.QName(c).localname
            if key=='MapEntry':
                value=c.find('{%s}Value'%etree.QName(c).namespace)
                obj[c.get('key')]=json.loads(value.text)
            else:
                obj[key]=value_from_xml(c,schema.get('properties',{}).get(key,{}),document,path)
        if elem.get('schemaRef'):
            obj['$schema']=elem.get('schemaRef')
        return obj
    if typ == 'boolean':
        return elem.text == 'true'
    if typ == 'integer':
        return int(elem.text)
    if typ == 'number':
        return float(elem.text)
    if typ is None:
        # Some schema branches use oneOf and therefore have no single primitive type.
        # Their original constraints are preserved in xs:appinfo, not inferred here.
        try:
            return json.loads(elem.text)
        except (ValueError,TypeError):
            return elem.text
    return elem.text if elem.text is not None else ''


class CanonicalParityTest(unittest.TestCase):
    def test_schema_count_and_yaml_semantics(self):
        originals=sorted(ROOT.glob('**/src/product/jsondefs/**/*'+JSON_SUFFIX))
        self.assertEqual(len(originals),56)
        for src in originals:
            with self.subTest(schema=src.name):
                ypath=Path(str(src).replace('/src/product/jsondefs/','/src/product/yamldefs/').replace(JSON_SUFFIX,YAML_SUFFIX))
                xpath=Path(str(src).replace('/src/product/jsondefs/','/src/product/xmldefs/').replace(JSON_SUFFIX,'.xsd'))
                self.assertTrue(ypath.is_file())
                self.assertTrue(xpath.is_file())
                self.assertFalse(Path(str(ypath)+'.meta.yml').exists())
                self.assertFalse(Path(str(xpath)+'.meta.yml').exists())
                canonical=json.loads(src.read_text())
                expected=copy.deepcopy(canonical)
                change_refs(expected,YAML_SUFFIX)
                yaml_definition=json.loads(ypath.read_text())
                self.assertEqual(yaml_definition,expected)
                jsonschema.Draft202012Validator.check_schema(yaml_definition)
                xsd=etree.parse(str(xpath))
                validator=etree.XMLSchema(xsd)
                self.assertIsNotNone(validator)
                app=xsd.find('.//{%s}canonicalJsonSchema'%AAC)
                self.assertIsNotNone(app)
                self.assertEqual(json.loads(app.text),canonical)

    def test_configuration_formats_and_validation(self):
        configs=sorted(p for p in ROOT.glob('**/src/product/config/**/*.yml') if not p.name.endswith(('.meta.yml','.meta.yaml')))
        self.assertEqual(len(configs),19)
        for source in configs:
            with self.subTest(config=str(source.relative_to(ROOT))):
                ydata=yaml.safe_load(source.read_text())
                self.assertIn('/api/yamldefs/',ydata['$schema'])
                yrel=ydata['$schema'].split('/api/yamldefs/',1)[1]
                yschema=next(iter(ROOT.glob('**/src/product/yamldefs/'+yrel)))
                data=json.loads(yschema.read_text())
                jsonschema.Draft202012Validator(data).validate(ydata)
                jfile=source.with_suffix('.json')
                xfile=source.with_suffix('.xml')
                self.assertTrue(jfile.is_file())
                self.assertTrue(xfile.is_file())
                jdata=json.loads(jfile.read_text())
                jrel=jdata['$schema'].split('/api/jsondefs/',1)[1]
                self.assertEqual(jrel,yrel.replace(YAML_SUFFIX,JSON_SUFFIX))
                jschema=next(iter(ROOT.glob('**/src/product/jsondefs/'+jrel)))
                canonical=json.loads(jschema.read_text())
                jsonschema.Draft202012Validator(canonical).validate(jdata)
                normalized=normalize_resources(copy.deepcopy(ydata),JSON_SUFFIX)
                normalized['$schema']=jdata['$schema']
                self.assertEqual(normalized,jdata)
                xpath=Path(str(jschema).replace('/src/product/jsondefs/','/src/product/xmldefs/').replace(JSON_SUFFIX,'.xsd'))
                xml=etree.parse(str(xfile))
                self.assertTrue(etree.XMLSchema(etree.parse(str(xpath))).validate(xml))
                decoded=value_from_xml(xml.getroot(),canonical,canonical,jschema)
                decoded['$schema']=jdata['$schema']
                decoded=normalize_resources(decoded,JSON_SUFFIX)
                self.assertEqual(decoded,jdata)

    def test_canonical_roots_do_not_contain_config_files(self):
        for kind_name,suffix in [('yamldefs',YAML_SUFFIX),('jsondefs',JSON_SUFFIX),('xmldefs','.xsd')]:
            for root in ROOT.glob('**/src/product/'+kind_name):
                unexpected=[p for p in root.rglob('*') if p.is_file() and not p.name.endswith((suffix,'.meta.yml','.meta.yaml'))]
                self.assertEqual(unexpected,[])


if __name__=='__main__':
    unittest.main(verbosity=2)
