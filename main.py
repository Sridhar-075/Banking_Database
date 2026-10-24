from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from fastapi import FastAPI, HTTPException, Request




@asynccontextmanager
async def lifespan(app: FastAPI):
    

    pool = ConnectionPool(
        conninfo="postgresql://postgres:postgres@localhost:5432/banking_db",
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=False,
    )

    pool.open()
    app.state.pool = pool

    try:
        yield
    finally:
        pool.close()


app = FastAPI(lifespan=lifespan)


@app.get("/customers")
def get_customers(request: Request):
    try:
        with request.app.state.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM customer")
                rows = cur.fetchall()

        return rows

    except psycopg.Error:
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch customers",
        )
