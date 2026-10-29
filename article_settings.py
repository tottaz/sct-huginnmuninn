"""Article limits shared by validation, preview, and scheduled analysis."""
DEFAULT_ARTICLE_LIMIT = 1


def article_limit(config, source=None):
    value = config.get('articles_per_site', DEFAULT_ARTICLE_LIMIT)
    if isinstance(source, dict) and source.get('articles_per_site') is not None:
        value = source['articles_per_site']
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError('Articles per site must be a whole number from 1 to 100.')
    return value
