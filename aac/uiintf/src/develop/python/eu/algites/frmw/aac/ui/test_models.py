from eu.algites.frmw.aac.core.presentation.api import AInDisplayContentFormat, AIcDisplayContent, AIcDisplayText
from eu.algites.frmw.aac.ui.api import (
    AInUiFieldType, AIcUiDisplay, AIcUiField, AIcUiFieldGroup, AIcUiForm, AIcUiPanel,
)


def test_form_flattens_groups_and_normalizes_human_facing_text():
    form = AIcUiForm("x", "X", (AIcUiFieldGroup("g", "G", (AIcUiField("a", "A", AInUiFieldType.STRING),)),))
    assert [field.id for field in form.fields] == ["a"]
    assert form.title == AIcDisplayText(text="X")
    assert form.groups[0].label == AIcDisplayText(text="G")
    assert form.fields[0].label == AIcDisplayText(text="A")


def test_display_content_and_panel_are_toolkit_neutral():
    content = AIcDisplayContent(
        content="# Details\n\nLong **formatted** text.",
        resource_key="test.details",
        format=AInDisplayContentFormat.MARKDOWN,
    )
    panel = AIcUiPanel(
        "details",
        title=AIcDisplayText(text="Details", resource_key="test.details.title"),
        displays=(AIcUiDisplay("body", content),),
    )
    assert panel.title.resource_key == "test.details.title"
    assert panel.displays[0].content.format is AInDisplayContentFormat.MARKDOWN
