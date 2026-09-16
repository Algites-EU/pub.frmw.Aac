from algites.lib.aac.uiintf import AInUiFieldType, AIcUiField, AIcUiFieldGroup, AIcUiForm


def test_form_flattens_groups():
    form = AIcUiForm("x", "X", (AIcUiFieldGroup("g", "G", (AIcUiField("a", "A", AInUiFieldType.STRING),)),))
    assert [field.id for field in form.fields] == ["a"]
