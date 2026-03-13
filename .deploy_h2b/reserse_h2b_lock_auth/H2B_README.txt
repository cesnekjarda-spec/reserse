H2B – Uzamčení Reserse auth

Co se změnilo:
- veřejná registrace je vypnutá (`allow_public_registration=False`)
- odkaz na registraci zmizel z UI
- `/register` nově ukazuje informaci, že účet vytváří administrátor
- admin má novou správu uživatelů na `/admin/users`
- admin může vytvořit usera/admina
- admin může aktivovat/deaktivovat účty
- bootstrap už automaticky nevytváří testovacího běžného uživatele

Důležité:
- výchozí admin účet se stále bootstrapuje podle env
- pokud chceš zachovat i bootstrap běžného usera, nastav `BOOTSTRAP_USER_ENABLED=true`
