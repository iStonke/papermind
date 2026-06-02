from app.services.document_types import DocumentTypeService


class CategoryService(DocumentTypeService):
    def list_categories(self, include_count: bool):
        return self.list_document_types(include_count)

    def create_category(self, payload):
        return self.create_document_type(payload)

    def get_category_or_404(self, category_id):
        return self.get_document_type_or_404(category_id)

    def update_category(self, category_id, payload):
        return self.update_document_type(category_id, payload)

    def delete_category(self, category_id) -> None:
        self.delete_document_type(category_id)
