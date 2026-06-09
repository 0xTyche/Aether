"""Aether data ingestion package.

Three families of fetchers feed the pipeline:
  - rss        : periodic RSS pull (central banks, wires)
  - binance    : Binance public WebSocket streams (crypto, tokenized stocks)
  - akshare_   : AKShare polling (A-shares / HK / FX / China macro)

A single `scheduler` orchestrates all periodic work.
"""
