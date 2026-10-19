# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # 10 · Telegram sending: tables
# MAGIC
# MAGIC **What this sets up** for sending the ready-made heat message from the website to Telegram:
# MAGIC
# MAGIC | Table | What it holds |
# MAGIC |---|---|
# MAGIC | `app_telegram_chats` | Which Telegram **groups or channels** a coordinator linked (or unlinked) — appended, never overwritten |
# MAGIC | `app_telegram_sends` | Every message sent: to which group, by whom, when, whether Telegram accepted it — the audit trail |
# MAGIC
# MAGIC **How a centre connects Telegram** (done once):
# MAGIC 1. The HeatGuard team creates a bot with **@BotFather** in Telegram and stores its token as the secret
# MAGIC    `heatguard/telegram_bot_token` (`databricks secrets put-secret heatguard telegram_bot_token`). The website reads it through the app
# MAGIC    resource `telegram-bot-token`; it never appears in code, logs or the browser.
# MAGIC 2. The coordinator adds the bot to the centre's Telegram group (for a channel: as an admin who can post) and sends any message there.
# MAGIC 3. In the website, **Settings → Telegram → Find my groups**, then **Link**.
# MAGIC
# MAGIC **Privacy:** only group and channel IDs and names are stored. Messages in private chats are ignored, so no individual's Telegram
# MAGIC account is recorded. Seniors and volunteers receive the message by joining the centre's group or channel.
# MAGIC
# MAGIC Safe to re-run: tables are only created if missing.

# COMMAND ----------

S = "workspace.heatguard"
APP_SP = "ed28dd47-4fc7-4926-b5b1-f76c47888390"   # heatguard-web service principal (client id)

spark.sql(f"""CREATE TABLE IF NOT EXISTS {S}.app_telegram_chats (
  chat_id STRING, title STRING, chat_type STRING COMMENT 'group / supergroup / channel', action STRING COMMENT 'link or unlink',
  by_email STRING, at TIMESTAMP)
COMMENT 'Telegram groups/channels linked to HeatGuard (append-only; the latest row per chat decides whether it is linked). No private chats.'""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {S}.app_telegram_sends (
  send_id STRING, client_send_id STRING COMMENT 'one per Send press, so retries never post twice', chat_id STRING, chat_title STRING,
  audience STRING, language STRING, text STRING, ok BOOLEAN, error STRING, by_email STRING, at TIMESTAMP)
COMMENT 'Audit trail of HeatGuard messages sent to Telegram groups/channels.'""")

for t in ("app_telegram_chats", "app_telegram_sends"):
    spark.sql(f"GRANT MODIFY ON TABLE {S}.{t} TO `{APP_SP}`")
print("Telegram tables ready")
