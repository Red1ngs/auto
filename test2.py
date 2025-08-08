import asyncio
import logging
from app.execution.managers.handlers_manager import handlers_manager
from app.execution.handlers import mining_handlers, balance_handlers, quiz_handlers, chapter_handlers
from app.execution.managers.cluster_executor import ClusterManager
from app.models.execution_models import ProfileTask

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Регистрация хэндлеров
modules = [mining_handlers, balance_handlers, quiz_handlers, chapter_handlers]
for module in modules:
    handlers_manager.register_handlers_from_module(module)
    
executor = ClusterManager()

def batched(iterable, size):
    """Разделить итерируемый объект на пакеты заданного размера"""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

async def setup_profiles_once():
    """
    Один раз настроить профили в кластерах.
    Избегаем постоянного переназначения.
    """
    profile_ids = ["54778"]  # Ваши профили
    proxy_ids = ["0"]
    
    # Назначаем профили на прокси равномерно
    for i, profile_id in enumerate(profile_ids):
        proxy_id = proxy_ids[i % len(proxy_ids)]
        await executor.assign_profile(profile_id, proxy_id)
        logger.info(f"Профиль {profile_id} назначен на прокси {proxy_id}")

async def create_tasks_with_assigned_proxy(count: int, profile_id: str, action: str, payload: dict = None) -> list:
    """
    Создать задачи с уже назначенным прокси.
    Не вызываем переназначение профилей.
    """
    # Получаем текущий прокси профиля
    proxy_id = await executor.get_profile_proxy(profile_id)
    if not proxy_id:
        # Если профиль не назначен, назначаем на дефолтный прокси
        proxy_id = "0"
        await executor.assign_profile(profile_id, proxy_id)
    
    tasks = []
    for i in range(count):
        task = ProfileTask(profile_id=profile_id, action=action, payload=payload or {})
        task.proxy_id = proxy_id  # Используем уже назначенный прокси
        tasks.append(task)
    
    logger.info(f"Создано {count} задач для профиля {profile_id} на прокси {proxy_id}")
    return tasks

async def execute_batch_optimized(batch_num: int, batch: list, timeout: float = 60.0):
    """Оптимизированное выполнение батча"""
    futures = []
    
    print(f"[Batch {batch_num}] Отправка {len(batch)} задач...")
    
    # Отправляем все задачи
    for i, task in enumerate(batch):
        try:
            future = await executor.submit_task(task)
            futures.append(future)
        except Exception as e:
            logger.error(f"Ошибка при submit_task для задачи {i+1}: {e}")
            failed_future = asyncio.Future()
            failed_future.set_exception(e)
            futures.append(failed_future)
    
    # Ждем результаты
    if futures:
        try:
            print(f"[Batch {batch_num}] Ожидание выполнения {len(futures)} задач...")
            
            results = await asyncio.wait_for(
                asyncio.gather(*futures, return_exceptions=True),
                timeout=timeout
            )
            
            # Обрабатываем результаты
            success_count = 0
            error_count = 0
            
            print(f"\n[Batch {batch_num}] Результаты:")
            for i, result in enumerate(results):
                print(result)
                if isinstance(result, Exception):
                    print(f"  Задача {i + 1}: ❌ Ошибка — {result}")
                    error_count += 1
                else:
                    print(f"  Задача {i + 1}: ✅ Успех — {result}")
                    success_count += 1
            
            print(f"[Batch {batch_num}] Итого: ✅ {success_count} успешно, ❌ {error_count} с ошибками\n")
            return success_count, error_count
            
        except asyncio.TimeoutError:
            print(f"[Batch {batch_num}] ⏰ Таймаут! Не все задачи завершились вовремя")
            for future in futures:
                if not future.done():
                    future.cancel()
            return 0, len(futures)
            
        except Exception as e:
            print(f"[Batch {batch_num}] ❗ Ошибка при gather: {e}")
            logger.exception("Detailed error in gather")
            return 0, len(futures)
    
    return 0, 0

async def main():
    try:
        # ВАЖНО: Сначала настраиваем профили один раз
        print("Настройка профилей в кластерах...")
        await setup_profiles_once()
        
        # Создаем задачи с уже назначенными прокси
        tasks = await create_tasks_with_assigned_proxy(1, "54778", "load_chapters", 
                                                       {"manga_id": "73849983"})
        
        total_success = 0
        total_errors = 0
        
        # Выполняем батчи
        for batch_num, batch in enumerate(batched(tasks, 10), start=1):
            success, errors = await execute_batch_optimized(batch_num, batch)
            total_success += success
            total_errors += errors
            
            # Небольшая пауза между батчами
            await asyncio.sleep(1)
            
        # Финальная статистика
        print("\n=== ИТОГОВАЯ СТАТИСТИКА ===")
        print(f"Всего успешных: {total_success}")
        print(f"Всего с ошибками: {total_errors}")
        
        # Статистика кластеров
        stats = await executor.get_all_stats()
        for proxy_id, cluster_stats in stats['clusters'].items():
            print(f"Кластер {proxy_id}: успехов={cluster_stats['success_count']}, "
                  f"ошибок={cluster_stats['error_count']}")
        
    except Exception as e:
        print(f"❗ Критическая ошибка в main(): {e}")
        logger.exception("Critical error in main")
    
    finally:
        print("✅ Обработка завершена")
        # Профили остаются в кластерах для дальнейшего использования

if __name__ == "__main__":
    asyncio.run(main())