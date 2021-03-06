#!/usr/bin/python3
from matcher.model import Place, Item, ItemCandidate
from matcher import database, user_agent_headers, matcher, wikidata
from matcher.view import app
from matcher.overpass import wait_for_slot, get_status  # noqa: F401
from time import sleep
import requests
import sys

def do_reindex(place, force=False):
    print(place.display_name)

    existing = {item.item_id: item.tags for item in place.items}
    all_tags = place.all_tags

    place.load_items()
    place.add_tags_to_items()
    print('tags updated')

    tag_change = False
    for item in place.items:
        old = existing.get(item.item_id)
        if old and set(item.tags) == set(old):
            continue
        tag_change = True
        print(item.qid, item.enwiki)
        if old:
            print('  old:', old)
        print('  new:', item.tags)

    if not force and not tag_change:
        print('no change')
        place.state = 'ready'
        database.session.commit()
        return

    place.wbgetentities()
    database.session.commit()

    print(sorted(place.all_tags))
    print(sorted(all_tags))
    sleep(10)

    tables = database.get_tables()
    expect = [place.prefix + '_' + t for t in ('line', 'point', 'polygon')]
    if not all(t in tables for t in expect) or place.all_tags != all_tags:
        if not place.overpass_done:
            oql = place.get_oql()
            overpass_url = 'https://overpass-api.de/api/interpreter'

            wait_for_slot()
            print('running overpass query')
            r = requests.post(overpass_url, data=oql, headers=user_agent_headers())
            print('overpass done')

            place.save_overpass(r.content)
        place.state = 'postgis'
        database.session.commit()

        print('running osm2pgsql')
        place.load_into_pgsql(capture_stderr=False)
        place.state = 'osm2pgsql'
        database.session.commit()

    conn = database.session.bind.raw_connection()
    cur = conn.cursor()

    q = place.items.filter(Item.entity.isnot(None)).order_by(Item.item_id)
    for item in q:
        candidates = matcher.find_item_matches(cur, item, place.prefix, debug=False)
        for i in (candidates or []):
            c = ItemCandidate.query.get((item.item_id, i['osm_id'], i['osm_type']))
            if not c:
                c = ItemCandidate(**i, item=item)
                database.session.add(c)
        print(len(candidates), item.label)
    place.state = 'ready'
    database.session.commit()

    conn.close()

def reindex_all(skip_places=None):
    q = Place.query.filter(Place.state.isnot(None), Place.state != 'ready')
    if skip_places:
        q = q.filter(~Place.osm_id.in_(skip_places))
    for place in q:
        do_reindex(place, force=True)


app.config.from_object('config.default')
with app.app_context():
    database.init_app(app)
    if len(sys.argv) > 1:
        place_id = sys.argv[1]
        place = Place.query.get(place_id)
        do_reindex(place, force=True)
    else:
        reindex_all()
