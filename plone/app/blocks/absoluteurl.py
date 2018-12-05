import json

from plone.tiles.absoluteurl import BaseTileAbsoluteURL
from plone.tiles.interfaces import ITileDataManager, ITileType
from zope.component import queryUtility


class TransientTileAbsoluteURL(BaseTileAbsoluteURL):
    """Absolute URL for a transient tile. Includes the tile traverser and
    tile data encoded in the query string.
    """

    def __str__(self):
        url = super(TransientTileAbsoluteURL, self).__str__()
        data = ITileDataManager(self.context).get()
        if data:
            tileType = queryUtility(ITileType, name=self.context.__name__)
            if tileType is not None and tileType.schema is not None:
                if '?' in url:
                    url += '&_tiledata=' + json.dumps(data)
                else:
                    url += '?_tiledata=' + json.dumps(data)
        return url
