# Hunter Futures Pro — research/pairlist-publishing CLI only.
# No exchange access, no network calls, no live trading: see AGENTS.md / PROJECT.md.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="hunter-futures-pro" \
      org.opencontainers.image.description="Agent-first crypto futures research and pairlist-publishing tool for Freqtrade" \
      org.opencontainers.image.source="https://github.com/volkanmidilli/hunter-futures-pro" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Only what's needed to build and install the `hunter` package — keeps the image free of
# tests/, docs/, specs/, and history that add nothing at runtime.
COPY pyproject.toml README.md LICENSE ./
COPY src/hunter ./src/hunter

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 1000 hunter
USER hunter

ENTRYPOINT ["hunter"]
CMD ["--help"]
