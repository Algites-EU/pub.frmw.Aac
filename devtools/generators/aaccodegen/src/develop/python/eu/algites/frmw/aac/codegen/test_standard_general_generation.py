from __future__ import annotations

import sys

from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry
from eu.algites.frmw.aac.core.capability.api import (
    AIcCapabilityRef, AIcCapabilityContract, AIcCapabilityOperation,
    AIcCapabilityOperationInteraction, AInCapabilityOperationInteractionKind as Kind, AIcSchemaRef)
from eu.algites.frmw.aac.codegen.aic_python_capability_binding_generator import AIcPythonCapabilityBindingGenerator
from eu.algites.frmw.aac.codegen.aic_python_data_entity_binding_generator import AIcPythonDataEntityBindingGenerator
from eu.algites.frmw.aac.core.invocation.aic_operation_completion import AIcOperationCompletion
from eu.algites.frmw.aac.core.invocation.ain_operation_completion_state import AInOperationCompletionState


def make_schemas():
    registry = AIcSchemaRegistry()
    for logical,fields in [('my-input', {'Name':{'type':'string'}}),('my-output',{'Accepted':{'type':'boolean'}})]:
        registry.register(logical+'_1.json',{
            '$schema':'https://json-schema.org/draft/2020-12/schema',
            'x-aac-schema-id':'_AAC.test.'+logical,'x-aac-schema-version':1,
            'type':'object','properties':fields,'required':list(fields),
        })
    return registry


def import_generated(tmp_path, result):
    for unit in result.schema_sources:
        assert unit.primary_type.fully_qualified_type_name
        dest = tmp_path/unit.relative_path
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(unit.source)
    sys.path.insert(0,str(tmp_path))
    for unit in result.schema_sources:
        if unit.type_name.startswith('AIcgd'):
            module = __import__(unit.primary_type.module_name,fromlist=[unit.type_name])
            assert getattr(module,unit.type_name)


def test_aac_general_two_stage_generation(tmp_path):
    schemas=make_schemas()
    contract=AIcCapabilityContract(AIcCapabilityRef('_AAC.capability.myExample',1),'_AAC',(
        AIcCapabilityOperation('run',(
            AIcCapabilityOperationInteraction(Kind.INPUT,AIcSchemaRef('_AAC.test.my-input',1)),
            AIcCapabilityOperationInteraction(Kind.FINAL_SUCCESS_STATE_RESULT,AIcSchemaRef('_AAC.test.my-output',1))
        )),
    ))
    result=AIcPythonCapabilityBindingGenerator(schemas).generate_sources(contract)
    assert len(result.schema_sources)==6
    assert 'class AIcgd' not in result.binding_source
    assert 'from eu.algites.frmw.aac.generated.aicgd_my_input_1 import AIcgdMyInput_1' in result.binding_source
    assert {unit.primary_type.type_role for unit in result.schema_sources}=={
        'SMART_DATA_OBJECT_TYPE','MUTABLE_INTERFACE_TYPE',
        __import__('eu.algites.tool.codegen.defs.ain_defs_name_role',fromlist=['AInDefsNameRole']).AInDefsNameRole.INTERFACE_TYPE,
    }
    import_generated(tmp_path,result)
    module=type(sys)('aac_generated_binding')
    exec(result.binding_source,module.__dict__)
    from eu.algites.frmw.aac.generated.aicgd_my_input_1 import AIcgdMyInput_1
    from eu.algites.frmw.aac.generated.aicgd_my_output_1 import AIcgdMyOutput_1
    req=AIcgdMyInput_1.from_mapping({'Name':'X'})
    assert req.getName()=='X'
    assert req.to_mapping()=={'Name':'X'}
    class DummyInteraction:
        def exception_factory(self): return None
        def set_exception_factory(self, factory): self.factory=factory
    class DummyHandle:
        def new_operation_interaction(self):return DummyInteraction()
        def invoke_completion(self, operation_id, arguments, **kwargs):
            assert operation_id=='run'
            assert arguments=={'Name':'X'}
            return AIcOperationCompletion(AInOperationCompletionState.SUCCESS,{'Accepted':True})
    caller=module.AIcgMyExampleCaller_1(DummyHandle())
    completion=caller.run_1(req)
    assert isinstance(completion.success_result,AIcgdMyOutput_1)
    assert completion.success_result.to_mapping()=={'Accepted': True}


def test_data_entity_extends_canonical_general_contract(tmp_path):
    schemas=make_schemas()
    result=AIcPythonDataEntityBindingGenerator(schemas).generate_sources('_AAC.test.my-input',1)
    import_generated(tmp_path,result)
    scope={}
    exec(result.binding_source,scope)
    view=scope['AIigMyInputDataEntityView_1']
    from eu.algites.frmw.aac.generated.aiig_my_input_1 import AIigMyInput_1
    assert issubclass(view,AIigMyInput_1)
    assert 'def get_name_1' not in result.binding_source
    class Site(view):
        def __init__(self):self.name=None
        def set_name_1(self,value):self.name=value
        def getName(self):return self.name
    obj=Site()
    codec=scope['AIcgMyInputCodec_1']()
    codec.deserialize_into({'Name':'Z'},obj)
    assert codec.serialize(obj)=={'Name':'Z'}
    assert obj.to_mapping()=={'Name':'Z'}
