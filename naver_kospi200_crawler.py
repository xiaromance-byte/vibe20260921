"""
네이버페이 증권(stock.naver.com/market/stock/kr)에서 코스피 시가총액 상위
200개 종목 데이터를 수집하는 스크립트.

중요 - 페이지 구조에 대한 설명:
    stock.naver.com/market/stock/kr 페이지는 Next.js 기반으로 완전히
    자바스크립트에서 렌더링된다. requests로 받은 최초 HTML에는 종목 표(<table>)가
    비어있는 스켈레톤 상태로만 들어있고, 실제 종목 데이터는 페이지가 브라우저에서
    로드된 후 내부적으로 아래 API를 호출해 JSON으로 채워 넣는다.

        https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize=100

    따라서 BeautifulSoup4만으로 stock.naver.com의 <table> 태그에서 바로 데이터를
    긁어올 수는 없다(빈 테이블만 파싱됨). 이 스크립트는
    1) BeautifulSoup4로 원본 페이지(stock.naver.com/market/stock/kr)를 그대로
       요청/파싱해 실제로 데이터가 비어 있음을 확인하고,
    2) 그 페이지가 내부적으로 사용하는 위 JSON API를 호출해 코스피 시가총액
       상위 200종목 데이터를 수집한다.

주의:
- API 응답 구조는 네이버 정책에 따라 바뀔 수 있다.
- 서버 부하 방지를 위해 요청 사이에 지연(REQUEST_DELAY)을 둔다.
- 학습/개인 연구 목적 외 상업적 대량 수집 시 네이버 이용약관을 반드시 확인할 것.
"""

import csv
import time

import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://stock.naver.com/market/stock/kr"
API_URL = "https://m.stock.naver.com/api/stocks/marketValue/KOSPI"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://stock.naver.com/",
}

TARGET_COUNT = 200
PAGE_SIZE = 100  # API가 허용하는 최대치(100). 2페이지 호출로 200종목 확보.
REQUEST_DELAY = 0.5


def inspect_rendered_page():
    """stock.naver.com 원본 페이지를 BeautifulSoup4로 파싱해 상태를 확인한다."""
    response = requests.get(PAGE_URL, headers=HEADERS, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else "(제목 없음)"
    rows = soup.select("table tbody tr")

    print(f"[페이지 확인] title = {title}")
    print(f"[페이지 확인] 정적 HTML 내 <table> 데이터 행 수 = {len(rows)}건 "
          f"(0이면 자바스크립트로만 렌더링된다는 뜻)")


def fetch_kospi_market_value(page, page_size):
    params = {"page": page, "pageSize": page_size}
    response = requests.get(API_URL, headers=HEADERS, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def collect_kospi_top200():
    results = []
    page = 1
    while len(results) < TARGET_COUNT:
        data = fetch_kospi_market_value(page, PAGE_SIZE)
        stocks = data.get("stocks", [])
        if not stocks:
            break

        for stock in stocks:
            results.append(
                {
                    "rank": len(results) + 1,
                    "code": stock.get("itemCode"),
                    "name": stock.get("stockName"),
                    "close_price": stock.get("closePrice"),
                    "change_price": stock.get("compareToPreviousClosePrice"),
                    "change_direction": (stock.get("compareToPreviousPrice") or {}).get("text"),
                    "change_rate(%)": stock.get("fluctuationsRatio"),
                    "volume": stock.get("accumulatedTradingVolume"),
                    "trading_value(백만원)": stock.get("accumulatedTradingValue"),
                    "market_cap(억원)": stock.get("marketValue"),
                    "url": stock.get("newPcUrl"),
                }
            )
            if len(results) >= TARGET_COUNT:
                break

        page += 1
        time.sleep(REQUEST_DELAY)

    return results


def save_to_csv(results, filename="kospi200_result.csv"):
    fieldnames = list(results[0].keys())
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n결과를 '{filename}' 파일로 저장했습니다. (총 {len(results)}건)")


def main():
    inspect_rendered_page()
    print()

    print("코스피 시가총액 상위 200종목 수집 중...")
    results = collect_kospi_top200()

    print(f"\n총 {len(results)}건 수집 완료. 상위 10종목:\n")
    for item in results[:10]:
        print(
            f"{item['rank']:>3}. {item['name']:<12} "
            f"{item['close_price']:>10}원  "
            f"{item['change_direction']:>4} {item['change_price']}"
            f"({item['change_rate(%)']}%)  "
            f"시총 {item['market_cap(억원)']}억"
        )

    save_to_csv(results)


if __name__ == "__main__":
    main()
