from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models.source import Source
from app.models.topic import Topic
from app.utils.text import slugify


SAMPLE_TOPICS = [
    {"name": "Finance", "description": "Osobní finance, banky, úvěry, spoření.", "price_czk": 29, "sort_order": 1},
    {"name": "Ekonomika", "description": "Makroekonomika, inflace, trhy a firmy.", "price_czk": 39, "sort_order": 2},
    {"name": "Politika", "description": "Domácí a zahraniční politické dění.", "price_czk": 35, "sort_order": 3},
]

# Měšec.cz veřejně uvádí RSS adresu pro nové články na stránce Exporty. citeturn1view1
SAMPLE_SOURCES = [
    {
        "topic_name": "Finance",
        "name": "Měšec.cz – články",
        "website_url": "https://www.mesec.cz/",
        "rss_url": "http://www.mesec.cz/rss/clanky/",
    },
]


def main():
    init_db()
    with SessionLocal() as db:
        topic_map = {}

        for item in SAMPLE_TOPICS:
            slug = slugify(item["name"])
            topic = db.scalar(select(Topic).where(Topic.slug == slug))
            if not topic:
                topic = Topic(
                    name=item["name"],
                    slug=slug,
                    description=item["description"],
                    price_czk=item["price_czk"],
                    sort_order=item["sort_order"],
                    is_active=True,
                )
                db.add(topic)
                db.commit()
                db.refresh(topic)
            topic_map[item["name"]] = topic

        for item in SAMPLE_SOURCES:
            topic = topic_map[item["topic_name"]]
            existing = db.scalar(
                select(Source).where(Source.topic_id == topic.id, Source.rss_url == item["rss_url"])
            )
            if not existing:
                source = Source(
                    topic_id=topic.id,
                    name=item["name"],
                    website_url=item["website_url"],
                    rss_url=item["rss_url"],
                    is_active=True,
                )
                db.add(source)
                db.commit()

    print("Sample topics and sources created.")


if __name__ == "__main__":
    main()
