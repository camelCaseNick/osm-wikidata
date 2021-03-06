from matcher.model import Item
from matcher.place import Place
from matcher import database

def simple_place():
    place = Place(place_id=1,
                  osm_type='way',
                  osm_id=1,
                  display_name='test place',
                  category='test',
                  type='test',
                  place_rank=1,
                  south=0, west=0, north=0, east=0)
    return place

def filter_tags(tags):
    ''' Filter out lifecycle prefixes like was: and disused: '''

    prefixes = ('disused', 'was', 'abandoned', 'demolished',
                'destroyed', 'ruins', 'historic')

    return {tag for tag in tags
            if not any(tag.startswith(prefix + ':') for prefix in prefixes)}

def test_add_tags_to_items(app):
    place = simple_place()

    item = Item(item_id=1,
                tags={'amenity=library'},
                location='Point(-2.62071 51.454)',
                categories=['Museums'])
    place.items.append(item)
    database.session.add(place)
    database.session.commit()

    place.add_tags_to_items()
    expect = {
        'tourism=attraction',
        'tourism=gallery',
        'tourism=museum',
        'historic=museum',
        'building=museum',
        'amenity=library',
    }

    assert filter_tags(item.tags) == expect
    assert filter_tags(place.all_tags) == expect

def test_place_country_code(app):
    place = simple_place()
    place.address = [{'type': 'state', 'name': 'New York'},
                     {'type': 'country', 'name': 'USA'},
                     {'type': 'country_code', 'name': 'us'}]
    assert place.country_code == 'us'
    assert place.get_address_key('missing key') is None

    place = simple_place()
    place.address = {'state': 'New York',
                     'country': 'USA',
                     'country_code': 'us'}
    assert place.country_code == 'us'
    assert place.get_address_key('missing key') is None
