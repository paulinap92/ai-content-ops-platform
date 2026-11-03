"""Transport previews follow the exact public website source, never guessed SQL."""
import pytest
import httpx
from fastapi import HTTPException
from canarias_site.services import inspection

@pytest.mark.asyncio
async def test_transport_uses_bounded_get_without_writing_or_opening_sql(monkeypatch):
 calls=[]
 class Client:
  def __init__(self,**kwargs):assert kwargs=={'timeout':12,'follow_redirects':False}
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def get(self,url,params):
   calls.append((url,params));return httpx.Response(200,json={'features':[{'type':'Feature','properties':{'name':'Puerto'},'geometry':{'type':'Point','coordinates':[-16,28]}}]},request=httpx.Request('GET',url))
 monkeypatch.setattr(inspection.httpx,'AsyncClient',Client)
 monkeypatch.setenv('CANARIAS_API_URL','https://public.example')
 result=await inspection.data_rows(None,'explore','ports','tenerife',0,25)
 assert result['count']==1 and result['rows'][0]['name']=='Puerto' and result['readonly']
 assert calls==[('https://public.example/api/regions/canarias/ports',{'island':'tenerife'})]
 assert (await inspection.data_rows(None,'explore','titsa-stops','el-hierro'))['count']==0
 assert (await inspection.data_rows(None,'explore','tilp-routes','tenerife'))['count']==0

@pytest.mark.asyncio
async def test_transport_failure_is_explicit_without_falling_back_to_empty_sql(monkeypatch):
 class Client:
  def __init__(self,**kwargs):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def get(self,*args,**kwargs):raise httpx.ConnectTimeout('isolated test')
 monkeypatch.setattr(inspection.httpx,'AsyncClient',Client)
 with pytest.raises(HTTPException) as error:await inspection.data_rows(None,'explore','airports','global')
 assert error.value.status_code==503
