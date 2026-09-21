"""
PyQt6 기반 GUI 뉴스 크롤러.

네이버 통합검색 결과 페이지에서 검색어에 해당하는 뉴스 기사 목록
(제목/언론사/요약/링크)을 수집하고, 네이버뉴스 링크가 있으면 본문까지 크롤링한다.
목록에서 기사를 클릭하면 상세(요약/본문)를 오른쪽/아래 영역에 보여주고,
CSV로 결과를 저장할 수 있다.

동작 방식:
- 검색 결과 페이지의 뉴스 카드는 각 <a> 태그의 data-nlog-area 속성값
  (nws_all.h.tit / h.prof / h.nav / h.body 등)으로 역할(제목/언론사/네이버뉴스 링크/요약)을
  구분할 수 있고, data-nlog-params 안의 "gdid" 값으로 같은 기사에 속한 태그들을 묶을 수 있다.

주의:
- 검색 결과 페이지의 HTML 구조는 네이버 정책/UI 개편에 따라 수시로 바뀔 수 있으므로
  코드가 동작하지 않으면 실제 페이지 구조를 다시 확인 후 셀렉터를 수정해야 한다.
- 서버 부하 방지를 위해 요청 사이에 지연(REQUEST_DELAY)을 둔다.
- 학습/개인 연구 목적 외 상업적 대량 수집 시 네이버 이용약관 및 robots.txt를 반드시 확인할 것.
"""

import csv
import json
import sys
import time
from collections import defaultdict
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

REQUEST_DELAY = 1.0  # 요청 간 간격(초)


def build_search_url(query):
    return (
        "https://search.naver.com/search.naver"
        f"?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={quote(query)}"
    )


def fetch_html(url, timeout=10):
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def parse_news_list(html):
    """검색 결과 페이지에서 뉴스 기사(제목/링크/네이버뉴스링크/언론사/요약)를 추출한다."""
    soup = BeautifulSoup(html, "html.parser")

    groups = defaultdict(dict)
    for a in soup.find_all("a", attrs={"data-nlog-area": True}):
        area = a["data-nlog-area"]
        if not area.startswith("nws_all.h."):
            continue

        role = area.rsplit(".", 1)[-1]  # tit / prof / nav / body / img ...
        params_raw = a.get("data-nlog-params")
        gdid = None
        if params_raw:
            try:
                gdid = json.loads(params_raw).get("gdid")
            except (json.JSONDecodeError, AttributeError):
                gdid = None

        if gdid:
            groups[gdid][role] = a

    news_items = []
    for roles in groups.values():
        tit_tag = roles.get("tit")
        if tit_tag is None:
            continue

        title_span = tit_tag.select_one(".sds-comps-text-type-headline1")
        title = (title_span or tit_tag).get_text(strip=True)
        link = tit_tag.get("href")

        prof_tag = roles.get("prof")
        press_span = prof_tag.select_one(".sds-comps-text-type-body2") if prof_tag else None
        press = press_span.get_text(strip=True) if press_span else ""

        nav_tag = roles.get("nav")
        naver_link = nav_tag.get("href") if nav_tag else None

        body_tag = roles.get("body")
        body_span = body_tag.select_one(".sds-comps-text-type-body1") if body_tag else None
        summary = body_span.get_text(strip=True) if body_span else ""

        news_items.append(
            {
                "title": title,
                "press": press,
                "link": link,
                "naver_link": naver_link,
                "summary": summary,
            }
        )

    return news_items


def fetch_article_body(item):
    """네이버뉴스 링크가 있으면 그 페이지에서, 없으면 원문 링크에서 본문을 크롤링한다."""
    url = item.get("naver_link") or item.get("link")
    if not url:
        return None

    try:
        html = fetch_html(url)
    except requests.RequestException:
        return None

    soup = BeautifulSoup(html, "html.parser")

    body = soup.select_one("#dic_area") or soup.select_one("#articleBodyContents")

    if body is None:
        article = soup.find("article")
        container = article if article else soup
        paragraphs = [p.get_text(strip=True) for p in container.find_all("p")]
        text = "\n".join(p for p in paragraphs if p)
        return text or None

    for unwanted in body.select("script, style, .end_photo_org, .ab_sub_alarm"):
        unwanted.decompose()

    return body.get_text("\n", strip=True)


def save_to_csv(results, filename):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["title", "press", "link", "naver_link", "summary", "content"]
        )
        writer.writeheader()
        writer.writerows(results)


class CrawlerWorker(QThread):
    progress = pyqtSignal(str)
    item_ready = pyqtSignal(dict)
    finished_all = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        try:
            url = build_search_url(self.query)
            self.progress.emit(f"검색 페이지 요청 중... ({url})")
            html = fetch_html(url)
        except requests.RequestException as exc:
            self.failed.emit(f"검색 페이지 요청 실패: {exc}")
            return

        news_items = parse_news_list(html)
        if not news_items:
            self.failed.emit("뉴스 기사를 찾지 못했습니다. 페이지 구조가 변경되었을 수 있습니다.")
            return

        self.progress.emit(f"검색된 뉴스 기사 수: {len(news_items)}건. 본문 수집 시작...")

        results = []
        for idx, item in enumerate(news_items, start=1):
            self.progress.emit(f"[{idx}/{len(news_items)}] '{item['title']}' 본문 수집 중...")
            item["content"] = fetch_article_body(item) or ""
            results.append(item)
            self.item_ready.emit(item)
            time.sleep(REQUEST_DELAY)

        self.progress.emit("완료.")
        self.finished_all.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 뉴스 크롤러")
        self.resize(1000, 640)

        self.results = []
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # 검색 영역
        search_layout = QHBoxLayout()
        self.query_input = QLineEdit("반도체")
        self.search_btn = QPushButton("검색")
        self.save_btn = QPushButton("CSV로 저장")
        self.save_btn.setEnabled(False)
        search_layout.addWidget(QLabel("검색어:"))
        search_layout.addWidget(self.query_input)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.save_btn)
        root_layout.addLayout(search_layout)

        # 목록 + 상세 영역
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["제목", "언론사"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.show_detail)
        splitter.addWidget(self.table)

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        splitter.addWidget(self.detail_view)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, stretch=1)

        # 상태 표시줄
        self.status_label = QLabel("검색어를 입력하고 검색 버튼을 누르세요.")
        root_layout.addWidget(self.status_label)

        self.search_btn.clicked.connect(self.start_search)
        self.save_btn.clicked.connect(self.save_csv)
        self.query_input.returnPressed.connect(self.start_search)

    def start_search(self):
        query = self.query_input.text().strip()
        if not query:
            QMessageBox.warning(self, "알림", "검색어를 입력하세요.")
            return

        self.table.setRowCount(0)
        self.detail_view.clear()
        self.results = []
        self.save_btn.setEnabled(False)
        self.search_btn.setEnabled(False)
        self.status_label.setText("크롤링을 시작합니다...")

        self.worker = CrawlerWorker(query)
        self.worker.progress.connect(self.status_label.setText)
        self.worker.item_ready.connect(self.add_item)
        self.worker.finished_all.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def add_item(self, item):
        self.results.append(item)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(item["title"]))
        self.table.setItem(row, 1, QTableWidgetItem(item["press"]))

    def show_detail(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row >= len(self.results):
            return
        item = self.results[row]

        html_parts = [
            f"<h3>{item['title']}</h3>",
            f"<p><b>언론사:</b> {item['press']}</p>",
            f"<p><b>링크:</b> <a href='{item['naver_link'] or item['link']}'>"
            f"{item['naver_link'] or item['link']}</a></p>",
            f"<p><b>요약:</b> {item['summary']}</p>",
            "<hr>",
            f"<pre style='white-space: pre-wrap;'>{item['content']}</pre>",
        ]
        self.detail_view.setHtml("".join(html_parts))

    def on_finished(self, results):
        self.results = results
        self.search_btn.setEnabled(True)
        self.save_btn.setEnabled(bool(results))
        self.status_label.setText(f"완료: 총 {len(results)}건 수집")

    def on_failed(self, message):
        self.search_btn.setEnabled(True)
        self.status_label.setText("오류가 발생했습니다.")
        QMessageBox.warning(self, "오류", message)

    def save_csv(self):
        if not self.results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV로 저장", "naver_news_result.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            save_to_csv(self.results, path)
            QMessageBox.information(self, "저장 완료", f"'{path}' 파일로 저장했습니다.")
        except OSError as exc:
            QMessageBox.warning(self, "저장 실패", str(exc))


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
