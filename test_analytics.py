from database import SessionLocal
import models
from datetime import datetime, timedelta
from sqlalchemy import func

db = SessionLocal()
now = datetime.now()
start_date = now - timedelta(days=7)

convs = db.query(models.BotConversation).count()
print("Bot convs:", convs)

msgs = db.query(models.ChatHistory).count()
print("Total messages:", msgs)

sents = db.query(models.Contact.lead_sentiment, func.count(models.Contact.id)).group_by(models.Contact.lead_sentiment).all()
print("Sentiments:", sents)

status = db.query(models.Contact.status, func.count(models.Contact.id)).group_by(models.Contact.status).all()
print("Statuses:", status)

