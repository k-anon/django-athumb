import re
from storages.backends.s3boto import S3BotoStorage
from boto.s3.connection import OrdinaryCallingFormat
from django.conf import settings


# Region configuration.
AWS_REGIONS = [
    'eu-west-1',
    'us-east-1',
    'us-west-1',
    'us-west-2',
    'sa-east-1',
    'ap-northeast-1',
    'ap-southeast-1',
]
AWS_REGION = getattr(settings, 'AWS_REGION', 'us-east-1')
REGION_RE = re.compile(r's3-(.+).amazonaws.com')


class S3DummyConnection(object):
    """
    A skeletal drop-in for S3Connection that implements basic methods for
    compatibility with boto.s3 classes (in particular, URL calling formats).
    """
    def get_path(self, path='/'):
        return path
DUMMY_CONNECTION = S3DummyConnection()


class S3BotoStorage_AllPublic(S3BotoStorage):
    """
    Same as S3BotoStorage, but defaults to uploading everything with a
    public acl. This has two primary benefits:

    1) Non-encrypted requests just make a lot better sense for certain things
       like profile images. Much faster, no need to generate S3 auth keys.
    2) Since we don't have to hit S3 for auth keys, this backend is much
       faster than S3BotoStorage, as it makes no attempt to validate whether
       keys exist.

    WARNING: This backend makes absolutely no attempt to verify whether the
    given key exists on self.url(). This is much faster, but be aware.
    """
    # URL calling format with an HTTPS-friendly default.
    calling_format = getattr(settings, 'AWS_S3_CALLING_FORMAT',
                             OrdinaryCallingFormat())

    def __init__(self, region=AWS_REGION, *args, **kwargs):
        self.host = self._get_host(region)
        super(S3BotoStorage_AllPublic, self).__init__(
            acl='public-read',
            querystring_auth=False,
            secure_urls=False,
            *args,
            **kwargs
        )

    @property
    def connection(self):
        return DUMMY_CONNECTION

    def _get_host(self, region):
        """
        Returns correctly formatted host. Accepted formats:

            * simple region name, eg 'us-west-1' (see list in AWS_REGIONS)
            * full host name, eg 's3-us-west-1.amazonaws.com'.
        """
        if 'us-east-1' in region:
            return 's3.amazonaws.com'
        elif region in AWS_REGIONS:
            return 's3-%s.amazonaws.com' % region
        elif region and not REGION_RE.findall(region):
            raise ImproperlyConfigured('AWS_REGION improperly configured!')
        # can be full host or empty string, default region
        return region

    def url(self, name):
        """
        Since we assume all public storage with no authorization keys, we can
        just simply dump out a URL rather than having to query S3 for new keys.
        """
        name = super(S3BotoStorage_AllPublic, self)._normalize_name(
            super(S3BotoStorage_AllPublic, self)._clean_name(name)
        )

        if self.custom_domain:
            return "%s//%s/%s" % (self.url_protocol, self.custom_domain, name)

        if self.host:
            server = self.host
        else:
            server = 's3.amazonaws.com'
        return self.calling_format.build_url_base(
            DUMMY_CONNECTION, self.url_protocol.rstrip(':'), server,
            self.bucket_name, name
        )
