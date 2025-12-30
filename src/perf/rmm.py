"""
RMM (RAPIDS Memory Manager) integration for unified GPU memory pool.
"""

import cupy as cp
try:
    import rmm
    from rmm.allocators.cupy import rmm_cupy_allocator
    RMM_AVAILABLE = True
except ImportError:
    RMM_AVAILABLE = False


def setup_rmm_pool(pool_size_gb: float = None) -> None:
    """
    Setup RMM pool allocator for CuPy.
    
    Args:
        pool_size_gb: Pool size in GB (None = auto)
    """
    if not RMM_AVAILABLE:
        print("Warning: RMM not available. Using default CuPy allocator.")
        return
    
    # Initialize RMM pool
    if pool_size_gb is not None:
        pool_size_bytes = int(pool_size_gb * 1024**3)
        rmm.reinitialize(
            pool_allocator=True,
            initial_pool_size=pool_size_bytes,
        )
    else:
        rmm.reinitialize(pool_allocator=True)
    
    # Set CuPy to use RMM
    cp.cuda.set_allocator(rmm_cupy_allocator)
    
    print(f"✓ RMM pool allocator initialized (size: {pool_size_gb} GB)")


def get_rmm_stats() -> dict:
    """
    Get RMM memory statistics.
    
    Returns:
        Dictionary with memory stats
    """
    if not RMM_AVAILABLE:
        return {'error': 'RMM not available'}
    
    try:
        # Try to get memory resource stats
        mr = rmm.mr.get_current_device_resource()
        
        # RMM pool resource has different API than base resource
        if hasattr(mr, 'get_memory_info'):
            stats = mr.get_memory_info()
            return {
                'allocated_bytes': stats[0],
                'free_bytes': stats[1],
                'allocated_gb': stats[0] / 1024**3,
                'free_gb': stats[1] / 1024**3,
            }
        else:
            # Fallback: query device memory via CUDA
            import cupy as cp
            free_mem, total_mem = cp.cuda.runtime.memGetInfo()
            return {
                'allocated_bytes': total_mem - free_mem,
                'free_bytes': free_mem,
                'allocated_gb': (total_mem - free_mem) / 1024**3,
                'free_gb': free_mem / 1024**3,
            }
    except Exception as e:
        return {'error': str(e)}

