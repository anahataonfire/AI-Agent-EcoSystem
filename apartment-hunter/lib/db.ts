import { PrismaClient } from '@prisma/client';
import { PrismaLibSql } from '@prisma/adapter-libsql';

const globalForPrisma = globalThis as unknown as {
    prisma: PrismaClient | undefined;
};

// For Prisma 7 with SQLite, we need to use the libsql adapter
const adapter = new PrismaLibSql({
    url: `file:${process.cwd()}/prisma/dev.db`,
});

export const prisma = globalForPrisma.prisma ?? new PrismaClient({ adapter });

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
