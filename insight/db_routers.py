class VectorDBRouter:
    vector_models = ['itemembedding', 'docvec']
    
    def db_for_read(self, model, **hints):
        if model._meta.model_name in self.vector_models:
            return 'vecdb'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.model_name in self.vector_models:
            return 'vecdb'
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name in self.vector_models:
            return db == 'vecdb'
        
        return db == 'default'
