"""Aether data ingestion package.

Fetchers feed the pipeline from two directions:

News
  - rss        : periodic RSS pull (Fed / ECB / BoJ / BoE press releases)
  - jin10      : 金十快讯 flash news over the vendor's MCP endpoint

Market data
  - binance    : Binance public WebSocket streams (crypto, tokenized stocks)
  - akshare_   : AKShare polling (A-shares / HK / FX / China macro)

`common` holds the parse DTO and the dedup-and-insert path every news
fetcher shares.

A single `scheduler` orchestrates all periodic work.
"""
