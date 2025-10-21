import json
import logging
from django.conf import settings
from django.db.models import Q
from .models import Product
from typing import List, Dict, Any

# Безопасный импорт openai
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

class SmartSearchService:
    """
    Сервис для умного поиска товаров с использованием ChatGPT API
    """
    
    def __init__(self):
        self.api_available = OPENAI_AVAILABLE
        self.api_configured = False
        
        if self.api_available:
            api_key = getattr(settings, 'OPENAI_API_KEY', None)
            if api_key and api_key.strip():
                openai.api_key = api_key.strip()
                self.api_configured = True
                logger.info("OpenAI API ключ настроен успешно")
            else:
                logger.warning("OPENAI_API_KEY не установлен в настройках")
        else:
            logger.warning("OpenAI библиотека не установлена. pip install openai==0.28.1")
    
    def get_all_products_for_context(self) -> List[Dict[str, Any]]:
        """
        Получает все товары из базы данных для передачи в контекст ChatGPT
        """
        products = Product.objects.all().values(
            'id', 'name', 'description', 'article'
        )
        
        product_context = []
        for product in products:
            product_info = {
                'id': product['id'],
                'name': product['name'] or '',
                'description': product['description'] or '',
                'article': product['article']
            }
            product_context.append(product_info)
        
        return product_context
    
    def create_enhanced_search_prompt(self, original_query: str, products: List[Dict[str, Any]]) -> str:
        """
        Создает промпт для ChatGPT с учетом только оригинального запроса
        """
        products_text = "\n".join([
            f"ID: {p['id']}, Название: {p['name']}, Описание: {p['description']}, Артикул: {p['article']}"
            for p in products
        ])
        
        prompt = f"""
Ты — эксперт по семантическому поиску товаров.

Поисковый запрос пользователя: "{original_query}"

Список доступных товаров:
{products_text}

Инструкции:
1. Сравни запрос с каждым товаром.
2. Используй знание синонимов и логических связей. 
   Например:
   - "украшение" → кольца, серьги, браслеты, ожерелья, кулоны
   - "сиденье" → стул, кресло, табурет
   - "освещение" → лампы, светильники, софтбоксы
   - "звук" → микрофоны, наушники, динамики
3. Включи товар, если есть хотя бы слабая логическая связь.
4. Если подходящих товаров нет, верни пустой список.

Верни результат строго в JSON формате:
{{
  "relevant_products": [список ID товаров],
  "reasoning": "объяснение связей"
}}
"""
        return prompt
    
    def search_with_chatgpt(self, query: str) -> List[int]:
        """
        Выполняет поиск товаров с помощью ChatGPT API
        """
        if not self.api_available or not self.api_configured:
            logger.warning("ChatGPT недоступен, используется fallback поиск")
            return self.fallback_search(query)
        
        try:
            products = self.get_all_products_for_context()
            if not products:
                return []
            
            prompt = self.create_enhanced_search_prompt(query, products)
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Ты эксперт по поиску. Всегда возвращай JSON с найденными товарами."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,
                temperature=0.2,  # <-- строгость, меньше фантазии
                timeout=30
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"ChatGPT ответ: {response_text[:200]}...")
            
            try:
                result = json.loads(response_text)
                product_ids = result.get("relevant_products", [])
                
                # Валидация ID
                existing_ids = set(Product.objects.values_list('id', flat=True))
                valid_ids = [pid for pid in product_ids if pid in existing_ids]
                
                if not valid_ids:
                    return self.fallback_search(query)
                
                return valid_ids
            
            except json.JSONDecodeError:
                logger.error("Ошибка JSON от ChatGPT, fallback")
                return self.fallback_search(query)
        
        except Exception as e:
            logger.error(f"Ошибка при обращении к ChatGPT: {e}")
            return self.fallback_search(query)
    
    def fallback_search(self, query: str) -> List[int]:
        """
        Резервный поиск (по совпадениям)
        """
        terms = query.lower().split()
        q_objects = Q()
        
        for term in terms:
            if len(term) > 2:
                q_objects |= (
                    Q(name__icontains=term) |
                    Q(description__icontains=term) |
                    Q(article__icontains=term)
                )
        
        if q_objects:
            return list(Product.objects.filter(q_objects).values_list("id", flat=True))
        return []
    
    def smart_search(self, query: str) -> List[Product]:
        """
        Главный метод умного поиска
        """
        if not query or not query.strip():
            return Product.objects.none()
        
        product_ids = self.search_with_chatgpt(query)
        
        if not product_ids:
            return Product.objects.none()
        
        products = Product.objects.filter(id__in=product_ids)
        product_dict = {p.id: p for p in products}
        
        ordered = [product_dict[pid] for pid in product_ids if pid in product_dict]
        return ordered

# Глобальный экземпляр
smart_search_service = SmartSearchService()
