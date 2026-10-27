"""Optional plain-text About page fields; does not change the legacy profile contract."""
from urllib.parse import unquote
from app import admin_auth as auth

LIMITS = {'page_title':200,'page_intro':1000,'about_heading':200,'about_body':10000,
          'current_heading':200,'current_project_label':200,'current_project_url':1000,
          'contact_heading':200,'contact_intro':2000}


def validate(value):
    if not isinstance(value,dict) or not set(value).issubset(LIMITS):
        raise auth.invalid_request()
    for key,text in value.items():
        if not isinstance(text,str) or len(text)>LIMITS[key] or '\x00' in text:
            raise auth.invalid_request()
        try:text.encode('utf-8')
        except UnicodeError:raise auth.invalid_request() from None
    url=value.get('current_project_url','')
    if url:
        if url.startswith('/'):
            decoded=unquote(url)
            if not url.startswith('/#/') or any(ord(c)<=32 or ord(c)==127 or c=='\\' for c in url+decoded):
                raise auth.invalid_request()
        else:
            from app.profile import _url
            _url(url,False)
    return dict(value)
