from novel_analyzer.services.steering_library_service import (
    SteeringLibraryService,
    SteeringRetrievalPayload,
)


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
    payload: SteeringRetrievalPayload = service.retrieve_pack(
        query_text="底层逆袭 账本修仙 灵气衰败 章尾更高层级机会",
        trope_docs=["xianxia-underdog-ledger"],
        worldview_docs=["aura-decline-tax-state"],
        audience_docs=["male-xianxia-commercial-hooks"],
    )
    assert payload["steering_pack"]["trope_axes"]
    assert payload["retrieval_meta"]["selected_trope_docs"] == ["xianxia-underdog-ledger"]
    assert payload["retrieval_meta"]["hit_reasons"]["trope"]["xianxia-underdog-ledger"]
    summaries = payload["retrieval_meta"]["selected_doc_summaries"]["trope"]
    assert summaries[0]["slug"] == "xianxia-underdog-ledger"
    assert summaries[0]["summary"]
    assert summaries[0]["trope_axes"]


def test_steering_library_service_can_rank_multiple_candidates() -> None:
    service = SteeringLibraryService()
    payload: SteeringRetrievalPayload = service.retrieve_pack(
        query_text="sect credit feudal order 克制成长型读者预期 阶层跃迁 家族 官府 宗门 认证 税制化王朝 克制成长",
        trope_docs=["xianxia-underdog-ledger", "clan-bureaucracy-power-climb"],
        worldview_docs=["aura-decline-tax-state", "sect-credit-feudal-order"],
        audience_docs=["male-xianxia-commercial-hooks", "cautious-growth-reader-signals"],
    )
    assert payload["retrieval_meta"]["selected_trope_docs"]
    assert payload["retrieval_meta"]["selected_worldview_docs"]
    assert payload["retrieval_meta"]["selected_audience_docs"]


def test_steering_library_service_tags_improve_query_matching() -> None:
    service = SteeringLibraryService()
    payload: SteeringRetrievalPayload = service.retrieve_pack(
        query_text="认证体系 制度压迫 信用秩序",
        worldview_docs=["aura-decline-tax-state", "sect-credit-feudal-order"],
    )
    assert payload["retrieval_meta"]["selected_worldview_docs"][0] == "sect-credit-feudal-order"
    hit_reasons = payload["retrieval_meta"]["hit_reasons"]["worldview"]["sect-credit-feudal-order"]
    assert any(reason.startswith("tag_") for reason in hit_reasons)


def test_steering_library_service_doc_summaries_include_tags() -> None:
    service = SteeringLibraryService()
    payload: SteeringRetrievalPayload = service.retrieve_pack(
        query_text="账本修仙 收益可见",
        trope_docs=["xianxia-underdog-ledger"],
    )
    summary = payload["retrieval_meta"]["selected_doc_summaries"]["trope"][0]
    assert "tags" in summary
    assert "账本修仙" in summary["tags"]


def test_steering_library_service_new_samples_are_retrievable() -> None:
    service = SteeringLibraryService()

    trope_payload: SteeringRetrievalPayload = service.retrieve_pack(
        query_text="回乡 打脸 旧账翻盘 门第反差",
        trope_docs=[
            "xianxia-underdog-ledger",
            "clan-bureaucracy-power-climb",
            "exile-return-face-reversal",
            "mercantile-alliance-resource-gamble",
        ],
    )
    assert trope_payload["retrieval_meta"]["selected_trope_docs"][0] == "exile-return-face-reversal"

    worldview_payload: SteeringRetrievalPayload = service.retrieve_pack(
        query_text="边军 灵市 军功兑换 黑市交换",
        worldview_docs=[
            "aura-decline-tax-state",
            "sect-credit-feudal-order",
            "frontier-garrison-spirit-market",
            "ancestral-contract-cultivation-law",
        ],
    )
    assert worldview_payload["retrieval_meta"]["selected_worldview_docs"][0] == "frontier-garrison-spirit-market"

    audience_payload: SteeringRetrievalPayload = service.retrieve_pack(
        query_text="多方算计 站队代价 情报反转",
        audience_docs=[
            "male-xianxia-commercial-hooks",
            "cautious-growth-reader-signals",
            "revenge-payoff-commercial-rhythm",
            "faction-intrigue-reader-signals",
        ],
    )
    assert audience_payload["retrieval_meta"]["selected_audience_docs"][0] == "faction-intrigue-reader-signals"
