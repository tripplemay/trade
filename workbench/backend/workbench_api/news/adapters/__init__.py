"""B033 news source adapters — SEC EDGAR (F002) + Yahoo RSS (F003).

Every adapter implements :class:`workbench_api.news.adapters.base.NewsAdapter`
and yields :class:`NewsItem` instances. The CLI / repository / snapshot
writer are source-agnostic; only the adapter knows how to talk to its
upstream HTTP endpoint.
"""

from workbench_api.news.adapters.base import NewsAdapter, NewsItem

__all__ = ["NewsAdapter", "NewsItem"]
