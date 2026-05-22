name: Sports Betting System Automation

on:
  workflow_dispatch:
  schedule:
    - cron: '0 11 * * *'  # Runs automatically at 6:00 AM EST
    - cron: '0 22 * * *'  # Runs automatically at 5:00 PM EST

jobs:
  run-algorithm:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository code
        uses: actions/checkout@v4

      - name: Set up Python Environment
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Data Stream Packages
        run: |
          python -m pip install --upgrade pip
          pip install requests

      - name: Execute Math Filters Backend
        env:
          ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}
        run: python main.py

      - name: Commit and Push Restructured Data
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add bets.json
          git commit -m "Automated backend sync [Skip GitHub Actions]" || exit 0
          git push
