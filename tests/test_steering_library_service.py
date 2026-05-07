from novel_analyzer.services.steering_library_service import SteeringLibraryService


def test_steering_library_service_assembles_pack_from_local_docs() -> None:
    service = SteeringLibraryService()
    pack = service.assemble_pack(
        trope_docs=["xianxia-underdog-ledger"],
        worldview_docs=["aura-decline-tax-state"],
        audience_docs=["male-xianxia-commercial-hooks"],
    )
    assert "底层逆袭" in pack["trope_axes"]
    assert any("灵气衰败" in item for item in pack["worldview_capsule"])
    assert any("资源取得过程比结果更重要" in item for item in pack["innovation_directives"])
    assert any("章尾最好有更高层级机会或压力" in item for item in pack["external_knowledge_refs"])
