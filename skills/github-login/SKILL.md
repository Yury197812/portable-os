# Skill: GitHub Quick Login

## Quick Login to GitHub via API Token

### Clone any repo
```bash
git clone https://ghp_REDACTED@github.com/Yury197812/REPO_NAME.git
```

### Push to repo
```bash
cd REPO_NAME
git remote set-url origin https://ghp_REDACTED@github.com/Yury197812/REPO_NAME.git
git push
```

### Check API status
```bash
curl -H "Authorization: token ghp_REDACTED" https://api.github.com/user
```

### List repos
```bash
curl -H "Authorization: token ghp_REDACTED" https://api.github.com/user/repos
```

### Create new repo
```bash
curl -X POST -H "Authorization: token ghp_REDACTED" https://api.github.com/user/repos -d '{"name":"REPO_NAME","private":true}'
```

## Credentials
- **Token**: `ghp_REDACTED`
- **Username**: Yury197812
- **Email**: apohob5@gmail.com

## Browser Login (if needed)
1. Go to https://github.com/login
2. Click "Continue with Google"
3. Email: apohob5@gmail.com
4. Password: [REDACTED-PASSWORD]
5. Confirm 2FA on phone (Tecno SPARK 20C)
