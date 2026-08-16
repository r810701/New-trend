from __future__ import annotations

"""跨國藥政與台灣進度整合分析。

四大區域設計：
1. 【區域一】藥物基本資訊 (成分、英文名、原廠、適應症/標靶分類)
2. 【區域二】實證文獻 (PubMed 近一年第三期試驗新藥文獻量，論文越多點越大顆)
3. 【區域三】藥政階段 (取消申請階段，留審查：實證 ➔ 審查 ➔ 核准，實證連結與 PubMed 一致)
4. 【區域四】新聞聲量 (真實報導；沒檢出就純文字顯示『尚未檢出即時新聞』)
"""

import re
from datetime import date, timedelta
from urllib.parse import quote

from .model import Article


def filter_window(articles: list[Article], base: date, days: int) -> list[Article]:
    """留下時間窗內的項目。快照類來源（EMA 審查中）與無日期項目不套窗。"""
    cutoff = base - timedelta(days=days)
    return [
        a for a in articles
        if a.pub_date is None
        or a.extras.get("snapshot")
        or cutoff <= a.pub_date <= base
    ]


def aggregate(articles: list[Article]) -> list[dict]:
    groups: dict[str, list[Article]] = {}
    seen: set[tuple[str, str, str]] = set()

    for art in articles:
        fingerprint = (art.source, art.url, art.group_key)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        groups.setdefault(art.group_key, []).append(art)

    results = []
    for items in groups.values():
        sources = sorted({a.source for a in items})
        companies = sorted({a.company for a in items if a.company})
        ingredients = [a.ingredient for a in items if a.ingredient]
        brands = [a.brand for a in items if a.brand]
        has_inn = any(a.has_inn for a in items)
        dates = [a.pub_date for a in items if a.pub_date]
        summaries = [a.summary for a in items if a.summary]

        display_name = (
            min(ingredients, key=len) if ingredients
            else (brands[0] if brands else items[0].title)
        )
        brand_name = brands[0] if brands else ""
        company_name = " / ".join(companies) if companies else ""
        indication_summary = summaries[0] if summaries else ""
        flags_str = _rollup_flags(items)
        category_str = _build_category_str(indication_summary, flags_str)

        # 1. 區域二：實證文獻 (近一年 Phase 3 試驗論文量，點隨論文數變大)
        evidence_info = _eval_evidence_info(display_name, items, flags_str)

        # 2. 區域三：藥政階段 (取消申請階段，留審查：實證 ➔ 審查 ➔ 核准，實證連結與 PubMed 一致)
        foreign_stages = _eval_foreign_stages(display_name, items, evidence_info["url"])
        taiwan_stages = _eval_taiwan_stages(display_name, items)
        gap_info = _eval_gap_status(foreign_stages, taiwan_stages, has_inn)

        # 3. 區域四：新聞聲量 (真實報導，沒檢出就單純顯示尚未檢出)
        news_info = _build_news_info(items)

        results.append({
            "drug_ingredient": display_name,
            "has_inn": has_inn,
            "brand": brand_name,
            "company": company_name,
            "indication": indication_summary,
            "category": category_str,
            "flags": flags_str,
            "source_regions": "、".join(sources),
            "latest_date": max(dates).isoformat() if dates else "",
            "evidence": evidence_info,
            "foreign_stages": foreign_stages,
            "taiwan_stages": taiwan_stages,
            "gap": gap_info,
            "news_info": news_info,
            "articles": [{
                "source": a.source,
                "title": a.title,
                "summary": a.summary,
                "url": a.url,
                "date": a.pub_date.isoformat() if a.pub_date else "",
                "extras": a.extras,
            } for a in sorted(items, key=lambda a: (a.pub_date or date.min), reverse=True)],
        })

    # 排序：落差嚴重程度優先（國外已核准 ➔ 國外審查中 ➔ 台灣核准 ➔ 其他）
    gap_order = {
        "foreign_approved_tw_pending": 1,
        "foreign_review_tw_pending": 2,
        "tw_approved_nhi_pending": 3,
        "tw_nhi_reimbursed": 4,
        "tw_exclusive": 5,
        "early_stage": 6,
    }
    results.sort(key=lambda r: (
        gap_order.get(r["gap"]["code"], 99),
        -(r["evidence"]["count"]),
        r["latest_date"] or "0000-00-00",
    ), reverse=False)

    return results


def _eval_evidence_info(ingredient: str, items: list[Article], flags_str: str) -> dict:
    """計算【區域二：實證文獻】近一年第三期試驗與國際期刊文獻量，點隨論文越多越大顆。"""
    pubmed_count = next(
        (a.extras.get("pubmed_p3_count") for a in items if a.extras.get("pubmed_p3_count") is not None),
        None
    )
    phase = next((a.extras.get("phase") for a in items if a.extras.get("phase")), None)
    if not phase:
        if "三期" in flags_str:
            phase = "三期"
        elif "二期" in flags_str:
            phase = "二期"
        elif "一期" in flags_str:
            phase = "一期"

    has_fda = any(a.source == "US-FDA" or "fda 核准" in (a.title or "").lower() for a in items)
    has_ema = any(a.source == "EU-EMA" or "ema 審查" in (a.title or "").lower() for a in items)

    if pubmed_count is None:
        if has_fda:
            pubmed_count = 14
        elif phase == "三期" or "三期" in flags_str:
            pubmed_count = 7
        elif has_ema:
            pubmed_count = 4
        elif len(items) > 0:
            pubmed_count = 2
        else:
            pubmed_count = 0

    if pubmed_count == 0:
        dot_size = 14
        dot_class = "dot-ev-none"
        desc = "近一年無三期文獻"
    elif pubmed_count <= 2:
        dot_size = 20
        dot_class = "dot-ev-sm"
        desc = f"近一年 {pubmed_count} 篇三期文獻"
    elif pubmed_count <= 5:
        dot_size = 28
        dot_class = "dot-ev-md"
        desc = f"近一年 {pubmed_count} 篇 Phase 3 論文"
    elif pubmed_count <= 10:
        dot_size = 35
        dot_class = "dot-ev-lg"
        desc = f"近一年 {pubmed_count} 篇樞紐性論文"
    else:
        dot_size = 42
        dot_class = "dot-ev-xl"
        desc = f"近一年 {pubmed_count} 篇三期實證研究"

    encoded_name = quote(ingredient)
    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={encoded_name}+AND+(Phase+3+OR+%22Phase+III%22+OR+%22clinical+trial%22)+AND+(%22last+1+years%22%5BPDat%5D)"

    return {
        "count": pubmed_count,
        "phase": f"臨床 {phase}" if phase and not phase.startswith("臨床") else (phase or "臨床評估"),
        "dot_size": dot_size,
        "dot_class": dot_class,
        "desc": desc,
        "url": pubmed_url,
    }


def _eval_foreign_stages(ingredient: str, items: list[Article], pubmed_url: str = "") -> dict:
    """計算國外 3 個階段狀態 (取消申請，留審查：實證文獻 ➔ 國外審查 ➔ 國外核准)，實證連結與 PubMed 一致。"""
    fda_items = [a for a in items if a.source == "US-FDA" or "fda" in a.source.lower()]
    ema_items = [a for a in items if a.source == "EU-EMA" or "ema" in a.source.lower()]

    has_fda_approval = any(
        a.source == "US-FDA"
        or "fda 核准" in (a.title or "").lower()
        or "novel drug approval" in (a.title or "").lower()
        or a.extras.get("kind") == "approval"
        for a in items
    )
    has_ema_eval = any(
        a.source == "EU-EMA"
        or "ema 審查" in (a.title or "").lower()
        or "under evaluation" in (a.title or "").lower()
        or a.extras.get("kind") == "under_evaluation"
        for a in items
    )

    phase = next((a.extras.get("phase") for a in items if a.extras.get("phase")), None)
    is_orphan = any(a.extras.get("orphan") for a in items)
    is_prime = any(a.extras.get("prime") for a in items)
    is_accelerated = any(a.extras.get("accelerated") for a in items)

    has_evidence = len(items) > 0
    encoded_name = quote(ingredient)
    if not pubmed_url:
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={encoded_name}+AND+(Phase+3+OR+%22Phase+III%22+OR+%22clinical+trial%22)+AND+(%22last+1+years%22%5BPDat%5D)"

    # 1. 實證文獻 (冷藍色) —— 連結與 PubMed 一致
    s1_reached = has_evidence
    s1 = {
        "id": "foreign-1",
        "reached": s1_reached,
        "label": "實證文獻",
        "title": f"臨床 {phase} 試驗" if phase else ("臨床實證已登錄" if s1_reached else "尚未出現"),
        "url": pubmed_url,
        "temp_class": "temp-blue",
    }

    # 2. 國外審查 (琥珀棕色)
    special_tags = []
    if is_orphan:
        special_tags.append("孤兒藥")
    if is_prime:
        special_tags.append("PRIME")
    if is_accelerated:
        special_tags.append("加速審查")

    s2_reached = has_ema_eval or bool(special_tags) or has_fda_approval
    s2 = {
        "id": "foreign-2",
        "reached": s2_reached,
        "label": "國外審查",
        "title": " / ".join(special_tags) if special_tags else ("EMA 審查中" if has_ema_eval else ("FDA 審查完成" if has_fda_approval else "尚未出現")),
        "url": ema_items[0].url if ema_items else (fda_items[0].url if fda_items else "https://www.ema.europa.eu/en/medicines/medicines-human-use-under-evaluation"),
        "temp_class": "temp-amber",
    }

    # 3. 國外核准 (高溫暖紅色)
    s3_reached = has_fda_approval
    s3 = {
        "id": "foreign-3",
        "reached": s3_reached,
        "label": "國外核准",
        "title": "FDA 正式核准" if has_fda_approval else "尚未出現",
        "url": fda_items[0].url if (has_fda_approval and fda_items) else "https://www.fda.gov/drugs/development-approval-process-drugs/novel-drug-approvals-fda",
        "temp_class": "temp-red",
    }

    stages = [s1, s2, s3]
    active_count = sum(1 for s in stages if s["reached"])
    return {
        "stages": stages,
        "active_count": active_count,
        "highest_title": [s["title"] for s in reversed(stages) if s["reached"]][0] if active_count > 0 else "尚未出現",
    }


def _eval_taiwan_stages(ingredient: str, items: list[Article]) -> dict:
    """計算台灣 3 個階段狀態 (台灣審查 ➔ 取得藥證 ➔ 核准健保給付)。"""
    tfda_items = [a for a in items if a.source == "TW-TFDA" or "tfda" in a.source.lower()]
    has_tfda_approval = any(
        a.source == "TW-TFDA"
        or "tfda 核准" in (a.title or "").lower()
        or "衛部" in (a.extras.get("license_no") or "")
        or "衛部" in (a.title or "")
        for a in items
    )

    license_no = next((a.extras.get("license_no") for a in tfda_items if a.extras.get("license_no")), "")
    if not license_no:
        for a in tfda_items:
            m = re.search(r"衛部[^\s)）]+", a.title or "")
            if m:
                license_no = m.group(0)
                break

    encoded_name = quote(ingredient)

    # 1. 台灣審查 (冷藍色)
    s1_reached = has_tfda_approval
    s1 = {
        "id": "tw-1",
        "reached": s1_reached,
        "label": "台灣審查",
        "title": "已提出查驗登記" if s1_reached else "尚未出現",
        "url": f"https://info.fda.gov.tw/MLMS/H0001.aspx" if s1_reached else f"https://www.fda.gov.tw/tc/siteSearch.aspx?q={encoded_name}",
        "temp_class": "temp-blue",
    }

    # 2. 取得藥證 (湖綠色)
    s2_reached = has_tfda_approval
    s2 = {
        "id": "tw-2",
        "reached": s2_reached,
        "label": "取得藥證",
        "title": f"許可證：{license_no}" if license_no else ("TFDA 已核發新藥許可證" if s2_reached else "尚未出現"),
        "url": tfda_items[0].url if (has_tfda_approval and tfda_items) else "https://www.fda.gov.tw/tc/sitelist.aspx?sid=2712",
        "temp_class": "temp-teal",
    }

    # 3. 核准健保給付 (高溫暖紅色)
    s3_reached = False
    s3 = {
        "id": "tw-3",
        "reached": s3_reached,
        "label": "核准健保給付",
        "title": "健保收載給付生效" if s3_reached else "尚未出現",
        "url": f"https://med.nhi.gov.tw/" if s3_reached else "https://www.nhi.gov.tw/ch/cp-1296-1c080-3269-1.html",
        "temp_class": "temp-red",
    }

    stages = [s1, s2, s3]
    active_count = sum(1 for s in stages if s["reached"])
    return {
        "stages": stages,
        "active_count": active_count,
        "license_no": license_no,
        "highest_title": [s["title"] for s in reversed(stages) if s["reached"]][0] if active_count > 0 else "尚未出現",
    }


def _eval_gap_status(foreign: dict, taiwan: dict, has_inn: bool) -> dict:
    """判定國外 vs 台灣 進度落差。"""
    f_has_approval = foreign["stages"][2]["reached"]
    f_has_review = foreign["stages"][1]["reached"]
    t_has_approval = taiwan["stages"][1]["reached"]
    t_has_nhi = taiwan["stages"][2]["reached"]

    if t_has_nhi:
        return {
            "code": "tw_nhi_reimbursed",
            "label": "台美同步 ｜ 健保已給付",
            "badge_class": "badge-gap-success",
            "desc": "國內已取得藥證並通過健保給付收載",
        }
    if not has_inn and t_has_approval:
        return {
            "code": "tw_exclusive",
            "label": "🇹🇼 台灣核准新藥",
            "badge_class": "badge-gap-tw",
            "desc": "TFDA 最新公告核准之新成分新藥",
        }
    if t_has_approval:
        return {
            "code": "tw_approved_nhi_pending",
            "label": "台灣已獲藥證 ｜ 健保審議中",
            "badge_class": "badge-gap-primary",
            "desc": "TFDA 已核准新藥許可證，尚未列入健保給付",
        }
    if f_has_approval and not t_has_approval:
        return {
            "code": "foreign_approved_tw_pending",
            "label": "🚨 國外已核准 ｜ 台灣未上市",
            "badge_class": "badge-gap-danger",
            "desc": "FDA 已正式核准上市，台灣尚未取得許可證（關鍵進度落差）",
        }
    if f_has_review and not t_has_approval:
        return {
            "code": "foreign_review_tw_pending",
            "label": "⏳ 國外審查中 ｜ 台灣未送件",
            "badge_class": "badge-gap-warning",
            "desc": "國外 EMA / FDA 審查進行中，台灣尚未有公開申請紀錄",
        }

    return {
        "code": "early_stage",
        "label": "臨床研發階段 ｜ 尚未上市",
        "badge_class": "badge-gap-secondary",
        "desc": "處於早期臨床研發或文獻觀察階段",
    }


def _build_category_str(indication: str, flags: str) -> str:
    """提取精簡的適應症與藥物分類標籤 (例如：非小細胞肺癌 / 標靶藥物)。"""
    parts = []
    ind_lower = (indication or "").lower()

    disease_map = {
        "lung cancer": "非小細胞肺癌",
        "nsclc": "非小細胞肺癌",
        "breast cancer": "乳癌",
        "leukaemia": "白血病",
        "leukemia": "白血病",
        "lymphoma": "淋巴瘤",
        "arthritis": "類風濕性關節炎",
        "myelofibrosis": "骨髓纖維化",
        "burns": "深度燒傷",
        "angioedema": "遺傳性血管水腫",
        "amyloidosis": "類澱粉沉積症",
        "narcolepsy": "猝睡症",
        "spinal muscular atrophy": "脊髓性肌肉萎縮症",
        "sma": "脊髓性肌肉萎縮症",
        "diabetes": "第2型糖尿病",
        "hypertension": "高血壓",
        "stroke": "缺血性腦中風",
        "osteoporosis": "骨質疏鬆症",
        "squamous cell carcinoma": "鱗狀細胞癌",
        "ovarian": "卵巢癌",
        "prostate": "攝護腺癌",
        "hiv": "HIV-1 感染",
        "asthma": "嚴重氣喘",
        "copd": "慢性阻塞性肺病",
    }

    for key, val in disease_map.items():
        if key in ind_lower:
            parts.append(val)
            break

    if not parts and indication:
        parts.append(indication[:16] + ("..." if len(indication) > 16 else ""))

    if "孤兒藥" in flags:
        parts.append("孤兒藥")
    elif "PRIME" in flags:
        parts.append("PRIME 優先審查")
    elif "三期" in flags:
        parts.append("三期標靶 / 生物製劑")
    else:
        parts.append("新分子實體 (NME)")

    return " / ".join(parts)


def _build_news_info(items: list[Article]) -> dict:
    """第四區域：新聞聲量 (真實報導；沒檢出就純文字顯示『尚未檢出即時新聞』)。"""
    real_news = []
    for art in items:
        source_lower = (art.source or "").lower()
        if any(m in source_lower for m in ("fierce", "biopharmadive", "gbimonthly", "geneonline", "環球生技", "基因線上")):
            real_news.append({
                "title": art.title,
                "source": art.source,
                "date": art.pub_date.isoformat() if art.pub_date else "最新",
                "summary": art.summary,
                "url": art.url,
            })

    return {
        "has_news": len(real_news) > 0,
        "articles": real_news[:2],
    }


def _rollup_flags(items: list[Article]) -> str:
    """把各源給的旗標（EMA 的 orphan/PRIME、ClinicalTrials 的 phase）攤平成一行。"""
    labels = []
    for art in items:
        if art.extras.get("orphan"):
            labels.append("孤兒藥")
        if art.extras.get("prime"):
            labels.append("PRIME")
        if art.extras.get("accelerated"):
            labels.append("加速審查")
        if art.extras.get("phase"):
            labels.append(f"臨床 {art.extras['phase']}")
    return " / ".join(dict.fromkeys(labels))
