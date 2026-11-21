"""Perintah admin dari terminal.

  python -m app.cli create-user --email a@b.c --name "Uji" --password rahasia123 --role pengelola
  python -m app.cli create-api-key --client "K02-kelompok-x"
  python -m app.cli list-api-keys
  python -m app.cli revoke-api-key 3
  python -m app.cli assign-manager --place-id 5 --user-id 2
  (akun yang dibuat lewat CLI langsung terverifikasi)

Di STB: docker compose exec core-service python -m app.cli <perintah>
"""
import argparse
import getpass
import sys

from .db import connect, init_db
from .identity import service


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("create-user")
    u.add_argument("--email", required=True)
    u.add_argument("--name", required=True)
    u.add_argument("--password", help="kosongkan untuk diminta secara interaktif")
    u.add_argument("--role", choices=["wisatawan", "pengelola", "admin"], default="wisatawan")
    k = sub.add_parser("create-api-key")
    k.add_argument("--client", required=True, help="nama kelompok pemakai")
    sub.add_parser("list-api-keys")
    r = sub.add_parser("revoke-api-key")
    r.add_argument("key_id", type=int)
    m = sub.add_parser("assign-manager")
    m.add_argument("--place-id", type=int, required=True)
    m.add_argument("--user-id", type=int, required=True)
    args = ap.parse_args(argv)

    init_db()
    db = connect()
    try:
        if args.cmd == "create-user":
            pw = args.password or getpass.getpass("Password: ")
            if len(pw) < 8:
                print("password minimal 8 karakter", file=sys.stderr)
                return 1
            user = service.create_user(db, args.email, args.name, pw, args.role, verified=True)
            print(f"dibuat: id={user['id']} {user['email']} ({user['role']})")
        elif args.cmd == "create-api-key":
            key = service.create_api_key(db, args.client, None)
            print(f"id={key['id']} client={key['client_name']}")
            print(f"API KEY (simpan sekarang, tidak bisa dilihat lagi): {key['api_key']}")
        elif args.cmd == "list-api-keys":
            for key in service.list_api_keys(db):
                state = "DICABUT" if key["revoked"] else "aktif"
                print(f"{key['id']:>3}  {key['key_prefix']}...  {key['client_name']:<30} {state:<8}"
                      f" dipakai {key['request_count']}x, terakhir {key['last_used_at'] or '-'}")
        elif args.cmd == "revoke-api-key":
            print("dicabut" if service.revoke_api_key(db, args.key_id) else "tidak ditemukan")
        elif args.cmd == "assign-manager":
            row = db.execute("SELECT role FROM users WHERE id = ?", (args.user_id,)).fetchone()
            if not row or row["role"] != "pengelola":
                print("user harus berperan pengelola", file=sys.stderr)
                return 1
            db.execute("UPDATE places SET manager_id = ? WHERE id = ?", (args.user_id, args.place_id))
            db.commit()
            print("ok")
    except service.IdentityError as e:
        print(f"gagal: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
