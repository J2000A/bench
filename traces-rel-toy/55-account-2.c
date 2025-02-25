// SKIP PARAM: --set ana.activated[+] apron --enable ana.sv-comp.functions --set ana.path_sens[+] threadflag --set ana.apron.domain polyhedra
// TODO: why does this need path-sensitive threadflag even with mutex-meet to succeed?
// three-variable relation
#include <assert.h>
#include <pthread.h>

extern int __VERIFIER_nondet_int();

int total;
int moneyA;
int moneyB;
pthread_mutex_t M = PTHREAD_MUTEX_INITIALIZER;

void *funA(void *arg) {
  while (1) {
    int transfer;
    transfer = __VERIFIER_nondet_int();
    if (transfer >= 0) {
      pthread_mutex_lock(&M);
      assert(moneyA >= 0);
      assert(moneyB >= 0);
      assert(moneyA + moneyB == total);

      if (transfer <= moneyA) {
        moneyA -= transfer;
        moneyB += transfer;
      }

      assert(moneyA >= 0);
      assert(moneyB >= 0);
      assert(moneyA + moneyB == total);
      pthread_mutex_unlock(&M);
    }
  }

  return NULL;
}

void *funB(void *arg) {
  while (1) {
    int transfer;
    transfer = __VERIFIER_nondet_int();
    if (transfer >= 0) {
      pthread_mutex_lock(&M);
      assert(moneyA >= 0);
      assert(moneyB >= 0);
      assert(moneyA + moneyB == total);

      if (transfer <= moneyB) {
        moneyB -= transfer;
        moneyA += transfer;
      }

      assert(moneyA >= 0);
      assert(moneyB >= 0);
      assert(moneyA + moneyB == total);
      pthread_mutex_unlock(&M);
    }
  }

  return NULL;
}

int main(int argc, char **argv) {
  total = __VERIFIER_nondet_int();
  moneyA = __VERIFIER_nondet_int();
  if (total >= 0 && moneyA >= 0 && moneyA <= total) {
    moneyB = total - moneyA;
    assert(moneyA >= 0);
    assert(moneyB >= 0);
    assert(moneyA + moneyB == total);

    pthread_t threadA;
    pthread_t threadB;
    pthread_create(&threadA, NULL, funA, NULL);
    pthread_create(&threadB, NULL, funB, NULL);

    pthread_mutex_lock(&M);
    assert(moneyA >= 0);
    assert(moneyB >= 0);
    assert(moneyA + moneyB == total);
    pthread_mutex_unlock(&M);
  }

  return 0;
}
