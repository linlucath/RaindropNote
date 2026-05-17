from fastapi import FastAPI


def create_app(lifespan) -> FastAPI:
    from .routers import note, provider, model, config, batch, bilibili, favorite

    app = FastAPI(title="BiliNote",lifespan=lifespan)
    app.include_router(note.router, prefix="/api")
    app.include_router(provider.router, prefix="/api")
    app.include_router(model.router,prefix="/api")
    app.include_router(config.router,  prefix="/api")
    app.include_router(batch.router, prefix="/api")
    app.include_router(bilibili.router, prefix="/api")
    app.include_router(favorite.router, prefix="/api")

    return app
