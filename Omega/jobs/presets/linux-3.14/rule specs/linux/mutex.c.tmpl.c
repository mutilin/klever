#include <linux/kernel.h>
#include <linux/mutex.h>
#include <linux/errno.h>
#include <verifier/rcv.h>
#include <verifier/set.h>

# for arg_sign in arg_signs
Set LDV_MUTEXES{{ arg_sign.id }};

/* MODEL_FUNC_DEF Check that mutex{{ arg_sign.text }} was not acquired and acquire it */
void ldv_mutex_acquire{{ arg_sign.id }}(struct mutex *lock)
{
  /* ASSERT Acquired mutex{{ arg_sign.text }} should be unacquired */
  ldv_assert(!ldv_set_contains(LDV_MUTEXES{{ arg_sign.id }}, lock));
  /* CHANGE_STATE Acquire mutex{{ arg_sign.text }} */
  ldv_set_add(LDV_MUTEXES{{ arg_sign.id }}, lock);
}

/* MODEL_FUNC_DEF Check that mutex{{ arg_sign.text }} was not acquired and nondeterministically acquire it */
int ldv_mutex_acquire_interruptible_or_killable{{ arg_sign.id }}(struct mutex *lock)
{
  /* ASSERT Acquired mutex{{ arg_sign.text }} should be unacquired */
  ldv_assert(!ldv_set_contains(LDV_MUTEXES{{ arg_sign.id }}, lock));
  /* OTHER Nondeterministically acquire mutex{{ arg_sign.text }} */
  if (ldv_undef_int())
  {
    /* MODEL_FUNC_CALL Acquire mutex{{ arg_sign.text }}  */
    ldv_mutex_acquire{{ arg_sign.id }}(lock);
    /* RETURN Successfully acquired mutex{{ arg_sign.text }} */
    return 0;
  }
  else
  {
    /* RETURN Could not acquire mutex{{ arg_sign.text }} */
    return -EINTR;
  }
}

/* MODEL_FUNC_DEF Say whether mutex{{ arg_sign.text }} was acquired */
int ldv_mutex_is_acquired{{ arg_sign.id }}(struct mutex *lock)
{
  /* OTHER Either mutex{{ arg_sign.text }} was acquired in this thread or nondeterministically decide whether it was done in another thread */
  if (ldv_set_contains(LDV_MUTEXES{{ arg_sign.id }}, lock) || ldv_undef_int())
  {
    /* RETURN Mutex{{ arg_sign.text }} was acquired in this or in another thread */
    return 1;
  }
  else
  {
    /* RETURN Mutex{{ arg_sign.text }} was not acquired anywhere */
    return 0;
  }
}

/* MODEL_FUNC_DEF Acquire mutex{{ arg_sign.text }} if it was not acquired before */
int ldv_mutex_try_acquire{{ arg_sign.id }}(struct mutex *lock)
{
  /* OTHER Mutex{{ arg_sign.text }} can be acquired if it was not already acquired */
  if (ldv_mutex_is_acquired{{ arg_sign.id }}(lock))
  {
    /* RETURN Mutex{{ arg_sign.text }} was already acquired */
    return 0;
  }
  else
  {
    /* MODEL_FUNC_CALL Acquire mutex{{ arg_sign.text }}  */
    ldv_mutex_acquire{{ arg_sign.id }}(lock);
    /* RETURN Successfully acquired mutex{{ arg_sign.text }} */
    return 1;
  }
}

/* MODEL_FUNC_DEF Decrease a given counter by one and if it becomes 0 check that mutex{{ arg_sign.text }} was not acquired and acquire it */
int ldv_mutex_decrement_and_acquire{{ arg_sign.id }}(atomic_t *cnt, struct mutex *lock)
{
  /* OTHER Decrease counter by one */
  cnt->counter--;

  /* OTHER Mutex{{ arg_sign.text }} can be acquired if counter becomes 0 */
  if (cnt->counter)
  {
    /* RETURN Counter is greater then 0, so mutex{{ arg_sign.text }} was not acquired */
    return 0;
  }
  else
  {
    /* ASSERT Acquired mutex{{ arg_sign.text }} should be unacquired */
    ldv_assert(!ldv_set_contains(LDV_MUTEXES{{ arg_sign.id }}, lock));
    /* MODEL_FUNC_CALL Acquire mutex{{ arg_sign.text }}  */
    ldv_mutex_acquire{{ arg_sign.id }}(lock);
    /* RETURN Successfully acquired mutex{{ arg_sign.text }} */
    return 1;
  }
}

/* MODEL_FUNC_DEF Check that mutex{{ arg_sign.text }} was acquired and release it */
void ldv_mutex_release{{ arg_sign.id }}(struct mutex *lock)
{
  /* ASSERT Released mutex{{ arg_sign.text }} should be acquired */
  ldv_assert(ldv_set_contains(LDV_MUTEXES{{ arg_sign.id }}, lock));
  /* CHANGE_STATE Release mutex{{ arg_sign.text }} */
  ldv_set_remove(LDV_MUTEXES{{ arg_sign.id }}, lock);
}
# endfor

/* MODEL_FUNC_DEF Make all mutexes unacquired at the beginning */
void ldv_initialize(void)
{
  # for arg_sign in arg_signs
  /* CHANGE_STATE No mutex is acquired at the beginning */
  ldv_set_init(LDV_MUTEXES{{ arg_sign.id }});
  # endfor
}

/* MODEL_FUNC_DEF Check that all mutexes are unacquired at the end */
void ldv_check_final_state(void)
{
  # for arg_sign in arg_signs
  /* ASSERT All acquired mutexes should be released before module unloading */
  ldv_assert(ldv_set_is_empty(LDV_MUTEXES{{ arg_sign.id }}));
  # endfor
}
