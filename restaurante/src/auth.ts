import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";

function normalizeEnvValue(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  let v = raw.trim();
  if (v.length >= 2 && ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'")))) {
    v = v.slice(1, -1);
  }
  return v;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      id: "credentials",
      credentials: {
        password: { label: "Contraseña", type: "password" },
      },
      authorize: async (credentials) => {
        const pwd = credentials?.password;
        if (typeof pwd !== "string" || pwd.length === 0) return null;

        const hash = normalizeEnvValue(process.env.ADMIN_PASSWORD_HASH);
        const plain = normalizeEnvValue(process.env.ADMIN_PASSWORD);

        // 1) Texto plano (útil en dev; en prod deja solo el hash y quita ADMIN_PASSWORD)
        if (plain) {
          if (pwd !== plain) return null;
        } else if (hash?.startsWith("$2") && hash.length >= 55) {
          const ok = await bcrypt.compare(pwd, hash);
          if (!ok) return null;
        } else {
          return null;
        }

        return {
          id: "admin",
          name: "Administración",
          email: "admin@clavo.local",
        };
      },
    }),
  ],
  session: { strategy: "jwt", maxAge: 60 * 60 * 8 },
  trustHost: true,
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.sub = user.id ?? token.sub;
        token.name = user.name;
        token.email = user.email;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = (token.sub as string) ?? session.user.id;
        if (token.name) session.user.name = token.name as string;
        if (token.email) session.user.email = token.email as string;
      }
      return session;
    },
  },
});
