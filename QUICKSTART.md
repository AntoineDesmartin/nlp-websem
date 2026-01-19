

```powershell
python3 -m venv .venv

source .venv/bin/activate

python -m pip install --upgrade pip
pip install pyshacl
``` 


```powershell
$env:OPENROUTER_API_KEY=""
```
sous mac
```
export OPENROUTER_API_KEY=""
```


```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```


http://localhost:8000













