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


def test_steering_library_service_retrieves_docs_with_hit_reasons() -> None:
    service = SteeringLibraryService()
    payload = service.retrieve_pack(
        query_text="底层逆袭 账本修仙 灵气衰败 章尾更高层级机会",
        trope_docs=["xianxia-underdog-ledger"],
        worldview_docs=["aura-decline-tax-state"],
        audience_docs=["male-xianxia-commercial-hooks"],
    )
    assert payload["steering_pack"]["trope_axes"]
    assert payload["retrieval_meta"]["selected_trope_docs"] == ["xianxia-underdog-ledger"]
    assert payload["retrieval_meta"]["hit_reasons"]["trope"]["xianxia-underdog-ledger"]
