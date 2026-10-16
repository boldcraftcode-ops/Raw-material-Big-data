import os
from fastapi import HTTPException
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse


class UploadBodyLimit:
    """Bound multipart input before Starlette can spool an unlimited file to disk."""
    def __init__(self,app,limit=None):
        self.app=app
        self.limit=limit if limit is not None else int(os.environ.get('RUBBER_MAX_FILE_BYTES',10*1024*1024))+1024*1024
        self.message='Ukuran permintaan melampaui batas file dan envelope multipart server.'

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or not scope.get('path','').startswith('/api/') or scope.get('method') not in ('POST','PATCH'):
            return await self.app(scope,receive,send)
        multipart=scope.get('path')=='/api/uploads'
        limit=self.limit if multipart else 1024*1024 if scope.get('path')=='/api/intake/events' else 128*1024
        headers=dict(scope.get('headers',[]))
        try: declared=int(headers.get(b'content-length',b'0'))
        except ValueError: declared=0
        if declared>limit:
            return await JSONResponse({'detail':self.message},status_code=413)(scope,receive,send)
        size=0
        async def bounded_receive():
            nonlocal size
            message=await receive()
            if message['type']=='http.request':
                size+=len(message.get('body',b''))
                if size>limit:
                    # MultiPartParser closes its temporary files on this exception.
                    if multipart: raise MultiPartException(self.message)
                    raise HTTPException(413,'Ukuran payload melampaui batas endpoint.')
            return message
        await self.app(scope,bounded_receive,send)
