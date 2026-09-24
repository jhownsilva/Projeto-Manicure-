# Auth Testing Playbook — Studio Gel & Beauty

## Admin credentials (seeded)
- Email: `jonathan.alexandre20@gmail.com`
- Password: `Salao@2026`

## Mongo verification
```
mongosh
use test_database
db.users.find({role:"admin"}).pretty()
```
- `password_hash` must start with `$2b$`
- Unique index on `email`

## Login flow (curl)
```
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
curl -c /tmp/c.txt -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"jonathan.alexandre20@gmail.com","password":"Salao@2026"}'
curl -b /tmp/c.txt "$API/api/auth/me"
```
Login returns `{token, user}` and sets httpOnly cookie `access_token`.
`/api/auth/me` returns the user object.

## Negative cases
- Wrong password → 401 `E-mail ou senha inválidos`
- Missing cookie/bearer → 401 `Não autenticado`

## Bearer support
```
TOKEN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"jonathan.alexandre20@gmail.com","password":"Salao@2026"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl "$API/api/auth/me" -H "Authorization: Bearer $TOKEN"
```
